from functools import wraps
from typing import Callable, Dict, List, Optional, Tuple, Union

from requests.exceptions import HTTPError, RequestException

from coinbitrage import bitlogging
from coinbitrage.exchanges.base import BaseExchangeAPI
from coinbitrage.exchanges.errors import ClientError, ServerError
from coinbitrage.settings import CURRENCIES, DEFAULT_QUOTE_CURRENCY, REQUESTS_TIMEOUT

from .formatter import BitExFormatter


log = bitlogging.getLogger(__name__)


class BitExAPIAdapter(BaseExchangeAPI):
    """Class for implementing REST API adapters using the BitEx library."""
    _api_class = None
    _formatter = BitExFormatter()
    _float_precision = 6

    def __init__(self, name: str, key_file: str, timeout: int = REQUESTS_TIMEOUT):
        super(BitExAPIAdapter, self).__init__(name)
        self._api = self._api_class(key_file=key_file, timeout=timeout)

    def __getattr__(self, name: str):
        return self._wrapped_bitex_method(name)

    def _wrapped_bitex_method(self, name: str):
        method = getattr(self._api, name)

        @wraps(method)
        def wrapper(*args, **kwargs):
            if 'quote_currency' in kwargs and args:
                base = args[0]
                quote = kwargs.pop('quote_currency')
                pair = self._formatter.pair(base, quote)
                args = (pair, *args[1:])
            elif 'currency' in kwargs:
                currency = kwargs.pop('currency')
                kwargs['currency'] = self._formatter.format(currency)

            # Convert float values to strings
            def float_to_str(val):
                if not isinstance(val, float):
                    return val
                return '{:.{prec}}'.format(str(val), prec=self._float_precision)

            args = [float_to_str(a) for a in args]
            kwargs = {kw: float_to_str(arg) for kw, arg in kwargs.items()}

            try:
                resp = method(*args, **kwargs)
            except RequestException as e:
                log.error(e, event_name='exchange_api.request_error')
                raise

            try:
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

            resp_data = resp.json()
            self.raise_for_exchange_error(resp_data)

            formatter = getattr(self._formatter, name)
            if not resp.formatted:
                log.debug('Possible uncaught exchange error: {response}', event_data={'response': resp_data},
                          event_name='exchange_api.possible_error')
                return formatter(resp_data)
            return formatter(resp.formatted)

        return wrapper

    def limit_order(self,
                    base_currency: str,
                    side: str,
                    price: float,
                    volume: float,
                    quote_currency: str = DEFAULT_QUOTE_CURRENCY,
                    **kwargs) -> Optional[str]:
        event_data = {'exchange': self.name, 'side': side, 'volume': volume, 'price': price,
                      'base': base_currency, 'quote': quote_currency}

        order_fn = self._wrapped_bitex_method('bid' if side == 'buy' else 'ask')
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

    def balance(self):
        return self._wrapped_bitex_method('balance')()

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

    def raise_for_exchange_error(self, response_data: dict):
        pass
