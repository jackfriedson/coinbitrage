import logging
from contextlib import contextmanager
from typing import Dict, List, Optional

from coinbitrage import bitlogging
from coinbitrage.exchanges import utils
from coinbitrage.exchanges.interfaces import PublicMarketAPI, PrivateExchangeAPI
from coinbitrage.exchanges.exceptions import APIException
from coinbitrage.exchanges.types import OHLC, OrderBook, Timestamp, Trade

from .api import KrakenAPI


log = bitlogging.getLogger(__name__)


currency_map = {
    'BTC': 'XXBT',
    'ETH': 'XETH',
    'USD': 'ZUSD',
}


@contextmanager
def handle_api_exception():
    try:
        yield
    except APIException as e:
        log.exception('Kraken returned an error -- %s', str(e), extra={
            'event_name': 'kraken_error',
            'event_data': {}
        })
        raise


class KrakenAPIAdapter(PublicMarketAPI, PrivateExchangeAPI):
    """Adapter from the core Kraken API to the exchange API interface."""

    def __init__(self, key_path: str) -> None:
        key, secret = utils.read_key_from(key_path)
        self.api = KrakenAPI(key, secret)
        self.last_txs = {}

    @staticmethod
    def currency_pair(base_currency, quote_currency):
        base_currency = currency_map.get(base_currency, base_currency)
        quote_currency = currency_map.get(quote_currency, quote_currency)
        return base_currency + quote_currency

    def _get_data(self, data_method, name, base_currency, quote_currency, since_last=True, **kwargs):
        if since_last:
            kwargs['since'] = self.last_txs.get(name)
        pair = self.currency_pair(base_currency, quote_currency)
        resp = data_method(pair, **kwargs)
        # self.last_txs[name] = resp['last']
        return resp[pair]

    # Market Info
    @handle_api_exception()
    def get_order_book(self,
                       base_currency: str,
                       quote_currency: str = 'USD') -> OrderBook:
        pair = self.currency_pair(base_currency, quote_currency)
        resp = self.api.get_order_book(pair)
        return self._format_order_book(resp[pair])

    @staticmethod
    def _format_order_book(data: Dict[str, list]) -> OrderBook:
        return {
            'asks': [{'price': d[0], 'amount': d[1]} for d in data['asks']],
            'bids': [{'price': d[0], 'amount': d[1]} for d in data['bids']],
        }

    @handle_api_exception()
    def get_trades(self,
                   base_currency: str,
                   quote_currency: str = 'USD',
                   since: Optional[Timestamp] = None) -> List[Trade]:
        kwargs = {}

        if since is not None:
            kwargs.update({'since': utils.to_unixtime(since)})

        data = self._get_data(self.api.get_recent_trades, 'trades', base_currency, quote_currency, **kwargs)
        return self._format_trades(data)

    @staticmethod
    def _format_trades(data: List[list]) -> List[Trade]:
        return [{
            'id': None,
            'timestamp': t[2],
            'price': float(t[0]),
            'amount': float(t[1]),
            'side': t[3],
            'type': t[4],
            'misc': t[5]
        } for t in data]

    @handle_api_exception()
    def get_ohlc(self,
                 base_currency: str,
                 quote_currency: str = 'USD',
                 interval: int = 1,
                 start: Optional[Timestamp] = None,
                 end: Optional[Timestamp] = None) -> List[OHLC]:
        since_last = start is None

        data = self._get_data(self.api.get_OHLC_data, 'ohlc', base_currency, quote_currency,
                              since_last=since_last, interval=interval)

        if end and end < data[0][0]:
            raise ValueError('Given end date is before the first data point')

        #  Only return data between `start` and `end`
        def date_filter(data_point):
            result = True
            if start is not None:
                result = result and data_point[0] >= start
            if end is not None:
                result = result and data_point[0] <= end
            return result

        data = filter(date_filter, data)

        # Format data as described in docstring
        return self._format_ohlc(data)

    @staticmethod
    def _format_ohlc(data: List[list]) -> List[OHLC]:
        return [{
            'datetime': pd.to_datetime(d[0], unit='s'),
            'open': float(d[1]),
            'high': float(d[2]),
            'low': float(d[3]),
            'close': float(d[4]),
            'volume': float(d[6])
        } for d in data]

    @handle_api_exception()
    def get_spread(self, base_currency, quote_currency='USD'):
        data = self._get_data(self.api.get_recent_spread_data, 'spread', base_currency, quote_currency)
        return [{
            'datetime': s[0],
            'bid': float(s[1]),
            'ask': float(s[2])
        } for s in data]

    # User Info
    @handle_api_exception()
    def get_orders_info(self, txids):
        """
        :returns: {
            txid: {order info}
        }
        """
        txid_string = ','.join(txids)
        resp = self.api.query_orders_info(txid_string)

        result = {}
        for txid, info in resp.items():
            order_info = {
                'txid': txid,
                'status': info['status'],
                'cost': float(info['cost']),
                'price': float(info['price']),
                'volume': float(info['vol']),
                'fee': float(info['fee'])
            }
            result[txid] = order_info

            # Log order close
            status = info['status']
            if status in ['closed', 'canceled', 'expired']:
                log.info('Got info on order %s', txid, extra={
                    'event_name': 'order_' + status,
                    'event_data': order_info
                })

        return result

    def get_order_info(self, txid):
        return self.get_orders_info([txid]).get(txid)

    # Orders

    @handle_api_exception()
    def _place_order(self,
                     order_type,
                     base_currency,
                     side,
                     volume,
                     quote_currency='USD',
                     **kwargs):
        pair = self.currency_pair(base_currency, quote_currency)
        resp = self.api.add_standard_order(pair, side, order_type, volume, **kwargs)

        txid = resp['txid']
        order_data = {
            'id': txid,
            'pair': pair,
            'side': side,
            'order_type': order_type,
            'volume': volume
        }
        order_data.update(kwargs)
        log.info('%s order placed: %s', order_type, txid, extra={
            'event_name': 'order_open',
            'event_data': order_data
        })

        return order_data

    def market_order(self, base_currency, side, volume, **kwargs):
        """
        :returns: txid of the placed order
        """
        return self._place_order('market', base_currency, side, volume, **kwargs)

    def limit_order(self, base_currency, side, price, volume, **kwargs):
        return self._place_order('limit', base_currency, side, volume, price=price, **kwargs)

    def stop_loss_order(self, base_currency, side, price, volume, **kwargs):
        return self._place_order('stop-loss', base_currency, side, volume, price=price, **kwargs)

    def stop_loss_limit_order(self, base_currency, side, stop_loss_price, limit_price, volume, **kwargs):
        return self._place_order('stop-loss-limit', base_currency, side, volume, price=stop_loss_price,
                                 price2=limit_price, **kwargs)

    def take_profit_order(self, base_currency, side, price, volume, **kwargs):
        return self._place_order('take-profit', base_currency, side, volume, price=price, **kwargs)

    def take_profit_limit_order(self, base_currency, side, take_profit_price, limit_price, volume, **kwargs):
        return self._place_order('take-profit-limit', base_currency, side, volume,
                                 price=take_profit_price, price2=limit_price, **kwargs)

    def trailing_stop_order(self, base_currency, side, trailing_stop_offset, volume, **kwargs):
        return self._place_order('trailing-stop', base_currency, side, volume,
                                 price=trailing_stop_offset, **kwargs)

    def trailing_stop_limit_order(self, base_currency, side, trailing_stop_offset, limit_offset,
                                  volume, **kwargs):
        return self._place_order('trailing-stop-limit', base_currency, side, volume,
                                 price=trailing_stop_offset, price2=limit_offset, **kwargs)

    def cancel_order(self, order_id):
        resp = self.api.cancel_open_order(txid=order_id)
        log.info('Canceled order %s', order_id, extra={
            'event_name': 'cancel_order',
            'event_data': resp
        })
