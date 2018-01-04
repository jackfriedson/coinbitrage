from typing import Optional

from bitex import Poloniex
from requests.exceptions import Timeout

from coinbitrage import bitlogging
from coinbitrage.exchanges.bitex import BitExAPIAdapter
from coinbitrage.exchanges.errors import ClientError, ServerError
from coinbitrage.settings import Defaults
from coinbitrage.utils import retry_on_exception

from .formatter import PoloniexFormatter


log = bitlogging.getLogger(__name__)


class PoloniexAPIAdapter(BitExAPIAdapter):
    _api_class = Poloniex
    formatter = PoloniexFormatter()

    def __init__(self, name: str, key_file: str):
        super(PoloniexAPIAdapter, self).__init__(name, key_file)
        self._fee = None

    @retry_on_exception(ServerError, Timeout)
    def fee(self,
            base_currency: str,
            quote_currency: str = Defaults.QUOTE_CURRENCY) -> float:
        if not self._fee:
            self._fee = float(self._wrap(self._api.fees)()['takerFee'])
        return self._fee

    def deposit_address(self, currency: str) -> dict:
        all_addresses = super(PoloniexAPIAdapter, self).deposit_address(currency)
        if currency in all_addresses:
            return {'address': all_addresses[currency]}
        return self._generate_new_address(currency)

    @retry_on_exception(ServerError, Timeout)
    def _generate_new_address(self, currency: str) -> str:
        params = {'currency': currency, 'command': 'generateNewAddress'}
        resp = self._wrap(self._api.private_query)('tradingApi', params=params)
        return {'address': resp['response']}

    def withdraw(self, *args, **kwargs) -> bool:
        if 'tag' in kwargs:
            kwargs.update({'paymentId': kwargs.pop('tag')})
        return super(PoloniexAPIAdapter, self).withdraw(*args, **kwargs)

    def raise_for_exchange_error(self, response_data: dict):
        if isinstance(response_data, dict):
            error_msg = response_data.get('error')
            if error_msg:
                log.warning('Poloniex API returned an error -- {message}',
                            event_name='poloniex_api.error', event_data={'message': error_msg})
                raise ClientError(error_msg)

    @retry_on_exception(ServerError, Timeout)
    def pairs(self):
        resp = self._wrap(self._api.ticker, format_resp=False)(None)
        return resp.keys()

    @retry_on_exception(ServerError, Timeout)
    def order(self, order_id: str) -> Optional[dict]:
        order = self._wrapped_bitex_method('orders')().get(order_id)
        if order is None:
            order = self._wrapped_bitex_method('order_trades')(order_id)
            order['is_open'] = False
        return order
