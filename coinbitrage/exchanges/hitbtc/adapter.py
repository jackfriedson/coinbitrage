from typing import Dict

from bitex import HitBtc

from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.bitex import BitExRESTAdapter
from coinbitrage.exchanges.mixins import PeriodicRefreshMixin, SeparateTradingAccountMixin


class HitBTCAdapter(BitExRESTAdapter, SeparateTradingAccountMixin):
    _api_class = HitBtc

    def __init__(self, name: str, key_file: str):
        super(HitBTCAdapter, self).__init__(name, key_file)

    def bank_balance(self) -> Dict[str, float]:
        resp = self._api.private_query('account/balance', method_verb='GET')
        return {val['currency']: float(val['available']) for val in resp.json()}

    def _transfer_between_accounts(self, to_trading: bool, currency: str, amount: float):
        direction = 'bankToExchange' if to_trading else 'exchangeToBank'
        params = {'currency': currency, 'amount': amount, 'type': direction}
        resp = self._api.private_query('account/transfer', method_verb='POST', params=params)
        return 'id' in resp.json()


class HitBTCClient(BaseExchangeClient, PeriodicRefreshMixin):
    name = 'hitbtc'
    _api_class = HitBTCAdapter

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        PeriodicRefreshMixin.__init__(self, 1)
