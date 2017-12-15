import logging
from functools import partial, wraps
from typing import Callable, Dict, List, Optional, Tuple, Union
from queue import Queue

from requests.exceptions import HTTPError, RequestException

from coinbitrage import bitlogging
from coinbitrage.exchanges.base import BaseExchangeAPI
from coinbitrage.exchanges.errors import ClientError, ServerError
from coinbitrage.exchanges.interfaces import WebsocketInterface
from coinbitrage.exchanges.types import OHLC, Order, OrderBook, Timestamp, Trade
from coinbitrage.settings import CURRENCIES, DEFAULT_QUOTE_CURRENCY, REQUESTS_TIMEOUT


log = bitlogging.getLogger(__name__)


class BitExFormatter(object):

    def __getattr__(self, name):
        return lambda x: x

    def ticker(self, data):
        result = {
            'bid': data[0],
            'ask': data[1],
            'high': data[2],
            'low': data[3],
            'open': data[4],
            'close': data[5],
            'last': data[6],
            'volume': data[7],
            'time': data[8]
        }
        result = {k: float(v) for k, v in result.items() if v}
        return result

    def trades(self, data) -> List[Trade]:
        return [{
            'id': None,
            'time': trade[0],
            'price': trade[1],
            'amount': trade[2],
            'side': trade[3]
        } for trade in data]

    def order_book(self, data) -> OrderBook:
        return {
            'asks': [{'price': ask[1], 'amount': ask[2]} for ask in data['asks']],
            'bids': [{'price': bid[1], 'amount': bid[2]} for bid in data['bids']]
        }

    def balance(self, data) -> Dict[str, float]:
        return {cur: float(bal) for cur, bal in data.items() if float(bal) != 0.}


class BitExRESTAdapter(BaseExchangeAPI):
    """Class for implementing REST API adapters using the BitEx library."""
    _api_class = None
    _formatter = BitExFormatter()
    _float_precision = 6
    _currency_map = {}

    def __init__(self, name: str, key_file: str):
        super(BitExRESTAdapter, self).__init__(name)
        self._api = self._api_class(key_file=key_file, timeout=REQUESTS_TIMEOUT)
        self._inverse_currency_map = {v: k for k, v in self._currency_map.items()}

    def __getattr__(self, name: str):
        return self._wrapped_bitex_method(name)

    def _wrapped_bitex_method(self, name: str):
        method = getattr(self._api, name)

        @wraps(method)
        def wrapper(*args, **kwargs):
            if 'quote_currency' in kwargs and args:
                base = args[0]
                quote = kwargs.pop('quote_currency')
                pair = self.pair(base, quote)
                args = (pair, *args[1:])
            elif 'currency' in kwargs:
                currency = kwargs.pop('currency')
                kwargs['currency'] = self._currency_map.get(currency, currency)

            # Convert float values to strings
            def float_to_str(val):
                if not isinstance(val, float):
                    return val
                return '{:.{prec}}'.format(str(val), prec=self._float_precision)

            args = [float_to_str(a) for a in args]
            kwargs = {kw: float_to_str(arg) for kw, arg in kwargs.items()}

            try:
                resp = method(*args, **kwargs)
                resp.raise_for_status()
            except HTTPError as e:
                event_data = {'status_code': resp.status_code, 'response': resp.content,
                              'method': method.__name__, 'args': args, 'kwargs': kwargs}
                if resp.status_code >= 400 and resp.status_code < 500:
                    log.error('Encountered an HTTP error ({status_code}): {response}',
                              event_name='exchange_api.http_error.client', event_data=event_data,)
                    raise ClientError(e)
                else:
                    log.warning('Encountered an HTTP error ({status_code}): {response}',
                                event_name='exchange_api.http_error.server', event_data=event_data)
                    raise ServerError(e)
            except RequestException as e:
                log.error(e, event_name='exchange_api.request_error')
                raise

            # TODO: implement a single error format across exchanges
            if not resp.formatted:
                log.warning('Possible exchange error: {response}', event_data={'response': resp.json()},
                            event_name='exchange_api.possible_error')

            formatter = getattr(self._formatter, name)
            return formatter(resp.formatted)

        return wrapper

    def limit_order(self,
                    base_currency: str,
                    side: str,
                    price: float,
                    volume: float,
                    quote_currency: str = DEFAULT_QUOTE_CURRENCY,
                    **kwargs) -> Optional[str]:
        order_fn_name = 'bid' if side == 'buy' else 'ask'
        order_fn = self._wrapped_bitex_method(order_fn_name)
        result = order_fn(base_currency, price, volume, quote_currency=quote_currency, **kwargs)
        event_data = {'exchange': self.name, 'side': side, 'volume': volume, 'price': price,
                      'base': base_currency, 'quote': quote_currency}
        if result:
            event_data.update({'order_id': result})
            log.info('Placed {side} order with {exchange} for {volume} {base} @ {price} {quote}',
                     event_data=event_data,
                     event_name='order.placed.success')
        else:
            log.info('Unable to place {side} order with {exchange} for {volume} {base} @ {price} {quote}',
                     event_name='order.placed.failure', event_data=event_data)
        return result

    def deposit_address(self, currency: str) -> str:
        return self._wrapped_bitex_method('deposit_address')(currency=currency)

    def withdraw(self, currency: str, address: str, amount: float, **kwargs) -> bool:
        assert amount >= CURRENCIES[currency]['min_transfer_size']
        event_data = {'exchange': self.name, 'amount': amount, 'currency': currency}
        result = self._wrapped_bitex_method('withdraw')(amount, address, currency=currency, **kwargs)
        if result:
            event_data.update(result)
            log.info('Withdrew {amount} {currency} from {exchange}', event_data=event_data,
                     event_name='exchange_api.withdraw.success')
        else:
            log.warning('Unable to withdraw {amount} {currency} from {exchange}', event_data=event_data,
                        event_name='exchange_api.withdraw.failure')
        return result

    def fmt_currency(self, currency: str, inverse: bool = False) -> str:
        cur_map = self._currency_map if not inverse else self._inverse_currency_map
        return cur_map.get(currency, currency)

    def pair(self, base_currency: str, quote_currency: str) -> str:
        base = self.fmt_currency(base_currency)
        quote = self.fmt_currency(quote_currency)
        return super(BitExRESTAdapter, self).pair(base, quote)

    def unpair(self, currency_pair: str) -> Tuple[str, str]:
        base, quote = super(BitExRESTAdapter, self).unpair(currency_pair)
        base = self.fmt_currency(base, inverse=True)
        quote = self.fmt_currency(quote, inverse=True)
        return base, quote


class BitExWSSAdapter(WebsocketInterface):
    """Class for implementing WSS adapters using the BitEx library."""
    _formatters = {}

    class QueueWrapper(object):
        """Wrapper around the BitEx websocket's data queue that adds additional
        funcitonality such as filtering and formatting messages.
        """
        def __init__(self, queue: Queue, formatters: Dict[str, Callable]):
            self._queue = queue
            self._formatters = formatters
            self._allowed_channels = set()
            self._allowed_pairs = set()

        def __getattr__(self, name: str):
            return getattr(self._queue, name)

        def get(self):
            message = self._queue.get()
            formatter = self._formatters[message[0]]
            return formatter(message)

    def __init__(self, websocket, *args, **kwargs):
        self._websocket = None
        self.queue = None
        self._init_websocket(websocket)
        super(BitExWSSAdapter, self).__init__(*args, **kwargs)

    def _init_websocket(self, websocket):
        self._websocket = websocket
        queue_wrapper = self.QueueWrapper(self._websocket.data_q, self._formatters)
        self._websocket.data_q = queue_wrapper
        self.queue = self._websocket.data_q

    def subscribe(self,
                  base_currency: str,
                  channel: str = 'ticker',
                  quote_currency: str = DEFAULT_QUOTE_CURRENCY):
        if not self._websocket.running:
            self._websocket.start()

    def shutdown(self):
        self._websocket.stop()

