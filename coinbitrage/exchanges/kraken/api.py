from collections import defaultdict
from typing import Dict, Optional

from bitex import Kraken
from requests.exceptions import ConnectTimeout, Timeout

from coinbitrage import bitlogging
from coinbitrage.exchanges.bitex import BitExAPIAdapter
from coinbitrage.exchanges.errors import ClientError, ExchangeError, ServerError
from coinbitrage.exchanges.mixins import ProxyCurrencyWrapper
from coinbitrage.settings import CURRENCIES, Defaults
from coinbitrage.utils import retry_on_exception

from .formatter import KrakenFormatter


log = bitlogging.getLogger(__name__)


KRAKEN_TIMEOUT = 60


class KrakenAPIAdapter(BitExAPIAdapter):
    _api_class = Kraken
    _error_cls_map = defaultdict(lambda: ClientError)
    _error_cls_map.update({'Service': ServerError,})
    formatter = KrakenFormatter()

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('timeout', KRAKEN_TIMEOUT)
        super(KrakenAPIAdapter, self).__init__(*args, **kwargs)

    def deposit_address(self, currency: str) -> dict:
        deposit_method = CURRENCIES[currency].get('kraken_method')
        if not deposit_method:
            raise NotImplementedError(f'Deposit address not implemented for {currency}')

        currency = self.formatter.format(currency)
        return super(KrakenAPIAdapter, self).deposit_address(currency, method=deposit_method)

    def raise_for_exchange_error(self, response_data: dict):
        errors = response_data.get('error')
        for error in errors:
            error_data = error.split(':')
            error_info, error_msg, error_extra = error_data[0], error_data[1], error_data[2:]
            severity, category = error_info[:1], error_info[1:]
            if severity == 'W':
                log.warning(f'Kraken API returned a warning -- {error}',
                            event_data={'category': category, 'message': error_msg, 'extra': error_extra},
                            event_name='kraken_api.warning')
            elif severity == 'E':
                log.warning(f'Kraken API returned an error -- {error}',
                            event_data={'category': category, 'message': error_msg, 'extra': error_extra},
                            event_name='kraken_api.error')
                if error_msg != 'Internal error':
                    error_cls = self._error_cls_map[category]
                    raise error_cls(error_msg)

    @retry_on_exception(ServerError, ConnectTimeout)
    def limit_order(self,
                    base_currency: str,
                    side: str,
                    price: float,
                    volume: float,
                    quote_currency: str = Defaults.QUOTE_CURRENCY,
                    **kwargs) -> Optional[str]:
        event_data = {'exchange': self.name, 'side': side, 'volume': volume, 'price': price,
                      'base': base_currency, 'quote': quote_currency}

        order_fn = self._wrap(self._api.bid if side == 'buy' else self._api.ask)
        kwargs.setdefault('timeout', Defaults.PLACE_ORDER_TIMEOUT)
        result = order_fn(base_currency, price, volume, quote_currency=quote_currency, **kwargs)

        if result:
            event_data.update({'order_id': result})
            log.info('Placed {side} order with {exchange} for {volume} {base} @ {price} {quote}',
                     event_data=event_data,
                     event_name='order.placed.success')
        else:
            log.info('Unable to place {side} order with {exchange} for {volume} {base} @ {price} {quote}',
                     event_name='order.placed.failure', event_data=event_data)
        return result

    @retry_on_exception(ServerError, Timeout)
    def order(self, order_id: str) -> Optional[dict]:
        order = self._wrap(self._api.closed_orders)().get(order_id)
        if order is None:
            order = self._wrap(self._api.orders)().get(order_id)
        return order

    def withdraw(self, currency: str, address: str, amount: float, **kwargs) -> bool:
        key = address
        if 'tag' in kwargs:
            kwargs.update({'paymentId': kwargs.pop('tag')})
        if currency == 'XRP' and 'paymentId' in kwargs:
            paymentId = kwargs.pop('paymentId')
            key += f'-{paymentId}'
        return super(KrakenAPIAdapter, self).withdraw(currency, key, amount, **kwargs)

class KrakenTetherAdapter(ProxyCurrencyWrapper):

    def __init__(self, *args, **kwargs):
        api = KrakenAPIAdapter(*args, **kwargs)
        super(KrakenTetherAdapter, self).__init__(api,
                                                  proxy_currency='USDT',
                                                  quote_currency='USD',
                                                  acceptable_bid=Defaults.USDT_BID,
                                                  acceptable_ask=Defaults.USDT_ASK)
