from typing import Optional

from bitex import Poloniex

from coinbitrage import bitlogging
from coinbitrage.exchanges.bitex import BitExAPIAdapter
from coinbitrage.exchanges.errors import ClientError
from coinbitrage.settings import DEFAULT_QUOTE_CURRENCY

from .formatter import PoloniexFormatter


log = bitlogging.getLogger(__name__)


class PoloniexAPIAdapter(BitExAPIAdapter):
    _api_class = Poloniex
    formatter = PoloniexFormatter()

    def __init__(self, name: str, key_file: str):
        super(PoloniexAPIAdapter, self).__init__(name, key_file)
        self._fee = None

    def fee(self,
            base_currency: str,
            quote_currency: str = DEFAULT_QUOTE_CURRENCY) -> float:
        if not self._fee:
            self._fee = float(self._api.fees().json()['takerFee'])
        return self._fee

    def deposit_address(self, currency: str) -> str:
        all_addresses = super(PoloniexAPIAdapter, self).deposit_address(currency)
        if currency in all_addresses:
            return all_addresses[currency]
        return self._generate_new_address(currency)

    def _generate_new_address(self, currency: str) -> str:
        params = {'currency': currency, 'command': 'generateNewAddress'}
        response = self._api.private_query('tradingApi', params=params)
        return response.json()['response']

    def limit_order(self, *args, fill_or_kill: bool = False, **kwargs) -> Optional[str]:
        if fill_or_kill:
            kwargs.update({'fill_or_kill': 1})
        return super(PoloniexAPIAdapter, self).limit_order(*args, **kwargs)

    def raise_for_exchange_error(self, response_data: dict):
        if isinstance(response_data, dict):
            error_msg = response_data.get('error')
            if error_msg:
                log.warning('Poloniex API returned an error -- {message}',
                            event_name='poloniex_api.error', event_data={'message': error_msg})
                raise ClientError(error_msg)

    def pairs(self):
        resp = self._api.ticker(None)
        return resp.json().keys()

    def order(self, order_id: str) -> Optional[dict]:
        order = self._wrapped_bitex_method('orders')().get(order_id)
        if order is None:
            order = self._wrapped_bitex_method('order_trades')(order_id)
            order['is_open'] = False
        return order
