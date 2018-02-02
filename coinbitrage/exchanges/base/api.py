import time
from functools import wraps
from typing import Any, Callable, Optional, Tuple

from requests.exceptions import HTTPError, RequestException

from coinbitrage import bitlogging
from coinbitrage.exchanges.errors import ClientError, ServerError
from coinbitrage.settings import Defaults
from coinbitrage.utils import format_floats, format_log_args

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

    def _wrap(self, func: Callable[[Any], Any], format_resp: bool = True) -> Any:
        """Wraps the given API function call in order to add logging, error handling, and formatting.

        :param func: the function to wrap
        :param format_resp: if set to false, the response is not formatted at all and just the parsed JSON is returned
        """
        @wraps(func)
        def wrapped(*args, **kwargs):
            args = format_floats(args, self.float_precision)
            kwargs = format_floats(kwargs, self.float_precision)

            log.debug('API call -- {exchange}.{method}{log_args}',
                      event_name='exchange_api.call',
                      event_data={'exchange': self.name, 'method': func.__name__, 'args': args,
                                  'kwargs': kwargs, 'log_args': format_log_args(args, kwargs)})

            try:
                resp = func(*args, **kwargs)
            except RequestException as e:
                log.error(e, event_name='exchange_api.request_error')
                raise
            try:
                resp.raise_for_status()
            except HTTPError as e:
                log_msg = '{exchange}.{method}{log_args} encountered an HTTP error ({status_code})'
                event_data = {'exchange': self.name, 'status_code': resp.status_code, 'method': func.__name__,
                              'log_args': format_log_args(args, kwargs), 'args': args, 'kwargs': kwargs}
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

            # Return formatted response
            if format_resp:
                formatter = getattr(self.formatter, func.__name__)
                return formatter(resp.formatted) if resp.formatted else formatter(resp_data)

            # Return parsed JSON
            return resp_data
        return wrapped

    def wait_for_fill(self, order_id: str, sleep: int = 3, timeout: int = Defaults.FILL_ORDER_TIMEOUT) -> Optional[dict]:
        """Wait for the order with the given ID to be filled and return the complete order data, or return None
        if it hasn't filled within `timeout` seconds.

        :param order_id: the ID of the order to wait for
        :param sleep: the number of seconds to wait between checks
        :param timeout: the number of seconds to wait before giving up and returning None
        """
        if not order_id:
            return None

        start_time = time.time()
        while (time.time() < start_time + timeout) if timeout is not None else True:
            order_info = self.order(order_id)
            if order_info and not order_info['is_open']:
                log.info('{exchange} order {order_id} closed', event_name='order.fill.success',
                         event_data={'exchange': self.name, 'order_id': order_id,
                                     'order_info': order_info})
                return order_info

            time.sleep(sleep)

        log.warning('Timed out waiting for {exchange} order {order_id} to fill after {timeout} seconds',
                    event_name='order.fill.timeout',
                    event_data={'exchange': self.name, 'order_id': order_id, 'timeout': timeout})
        return None

    def raise_for_exchange_error(self, resp_data: dict):
        pass

    #  Following methods must be overridden by subclasses

    def ticker(self, base_currency: str, quote_currency: str = Defaults.QUOTE_CURRENCY):
        raise NotImplementedError

    def deposit_address(self, currency: str) -> dict:
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
                    quote_currency: str = Defaults.QUOTE_CURRENCY,
                    **kwargs) -> Optional[str]:
        raise NotImplementedError

    def order(self, order_id: str) -> Optional[dict]:
        raise NotImplementedError
