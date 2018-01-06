import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import asyncio
from requests.exceptions import HTTPError, ConnectTimeout, RequestException, ReadTimeout, Timeout

from coinbitrage import bitlogging
from coinbitrage.exchanges.base import BaseExchangeAPI
from coinbitrage.exchanges.errors import ClientError, ServerError
from coinbitrage.settings import CURRENCIES, Defaults
from coinbitrage.utils import retry_on_exception

from .formatter import BitExFormatter


log = bitlogging.getLogger(__name__)


class BitExAPIAdapter(BaseExchangeAPI):
    """Class for implementing REST API adapters using the BitEx library."""
    _api_class = None
    formatter = BitExFormatter()

    def __init__(self, name: str, key_file: str, timeout: int = Defaults.HTTP_TIMEOUT):
        super(BitExAPIAdapter, self).__init__(name)
        self._api = self._api_class(key_file=key_file, timeout=timeout)

    def __getattr__(self, name: str):
        attr = getattr(self._api, name)
        if not callable(attr):
            return attr
        return retry_on_exception(ServerError, ConnectTimeout)(self._wrap(attr))

    def _wrap(self, func: Callable[[Any], Any], format_resp: bool = True) -> Any:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Format args as expected by Bitex
            if 'quote_currency' in kwargs and args:
                base = args[0]
                quote = kwargs.pop('quote_currency')
                pair = self.formatter.pair(base, quote)
                args = (pair, *args[1:])
            elif 'currency' in kwargs:
                currency = kwargs.pop('currency')
                kwargs['currency'] = self.formatter.format(currency)
            return super(BitExAPIAdapter, self)._wrap(func, format_resp=format_resp)(*args, **kwargs)
        return wrapper

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
    def ticker(self, base_currency: str, quote_currency: str = Defaults.QUOTE_CURRENCY):
        return self._wrap(self._api.ticker)(base_currency, quote_currency=quote_currency)

    @retry_on_exception(ServerError, Timeout)
    def balance(self):
        return self._wrap(self._api.balance)()

    @retry_on_exception(ServerError, Timeout)
    def deposit_address(self, currency: str, **kwargs) -> dict:
        return self._wrap(self._api.deposit_address)(currency=currency, **kwargs)

    @retry_on_exception(ServerError, Timeout)
    def order(self, order_id: str) -> Optional[dict]:
        return self._wrap(self._api.order)(order_id)

    @retry_on_exception(ServerError, ConnectTimeout)
    def withdraw(self, currency: str, address: str, amount: float, **kwargs) -> bool:
        event_data = {'exchange': self.name, 'amount': amount, 'currency': currency}
        result = self._wrap(self._api.withdraw)(amount, address, currency=currency, **kwargs)
        if result:
            event_data.update(result)
            log.info('Withdrew {amount} {currency} from {exchange}', event_data=event_data,
                     event_name='exchange_api.withdraw.success')
        else:
            log.warning('Unable to withdraw {amount} {currency} from {exchange}', event_data=event_data,
                        event_name='exchange_api.withdraw.failure')
        return result

