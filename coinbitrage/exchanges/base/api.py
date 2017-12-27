from functools import wraps
from typing import Optional, Tuple

from requests.exceptions import HTTPError, RequestException

from coinbitrage import bitlogging
from coinbitrage.exchanges.errors import ClientError, ServerError
from coinbitrage.settings import DEFAULT_ORDER_FEE, DEFAULT_QUOTE_CURRENCY
from coinbitrage.utils import format_float

from .formatter import BaseFormatter


log = bitlogging.getLogger(__name__)


class BaseExchangeAPI(object):
    """An exchange's REST API. Handles making requests, formatting responses, parsing errors
    and raising them.
    """
    formatter = BaseFormatter()
    float_precision = 6

    def __init__(self, name: str):
        self.name = name

    def _wrap(self, func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            args = tuple([format_float(a, self.float_precision) for a in args])
            kwargs = {kw: format_float(arg, self.float_precision) for kw, arg in kwargs.items()}

            log_args = tuple(list(args) + ['{}={}'.format(kw, arg) for kw, arg in kwargs.items()])
            log.debug('API call -- {exchange}.{method}{log_args}',
                      event_name='exchange_api.call',
                      event_data={'exchange': self.name, 'method': func.__name__, 'args': args,
                                  'kwargs': kwargs, 'log_args': log_args})

            try:
                resp = func(*args, **kwargs)
            except RequestException as e:
                log.error(e, event_name='exchange_api.request_error')
                raise
            try:
                resp.raise_for_status()
            except HTTPError as e:
                log_msg = '{exchange} encountered an HTTP error ({status_code})'
                event_data = {'exchange': self.name, 'status_code': resp.status_code,
                              'method': func.__name__, 'args': args, 'kwargs': kwargs}
                if 'application/json' in resp.headers['Content-Type']:
                    log_msg += ': {error_message}'
                    event_data['error_message'] = resp.json()
                if resp.status_code >= 400 and resp.status_code < 500:
                    log.error(log_msg, event_name='exchange_api.http_error.client', event_data=event_data)
                    raise ClientError(e)
                else:
                    log.warning(log_msg, event_name='exchange_api.http_error.server', event_data=event_data)
                    raise ServerError(e)

            resp_data = resp.json()
            self.raise_for_exchange_error(resp_data)
            formatter = getattr(self.formatter, func.__name__)
            return formatter(resp.formatted) if resp.formatted else formatter(resp_data)
        return wrapped

    def deposit_address(self, currency: str) -> str:
        raise NotImplementedError

    def balance(self):
        raise NotImplementedError

    def withdraw(self, currency: str, address: str, amount: float, **kwargs) -> bool:
        raise NotImplementedError

    def limit_order(self,
                    base_currency: str,
                    side: str,
                    price: float,
                    volume: float,
                    quote_currency: str = DEFAULT_QUOTE_CURRENCY,
                    **kwargs) -> Optional[str]:
        raise NotImplementedError

    async def wait_for_fill(self, order_id: str, sleep: int = 1, timeout: int = 60, do_async: bool = False):
        raise NotImplementedError
