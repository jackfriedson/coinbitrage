from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.mixins import PeriodicRefreshMixin

from .api import BitfinexAPIAdapter


class BitfinexClient(BaseExchangeClient, PeriodicRefreshMixin):
    name = 'bitfinex'
    _api_class = BitfinexAPIAdapter

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        PeriodicRefreshMixin.__init__(self, 6)

    def init(self):
        self.supported_pairs = self.api.pairs()
        self.currency_info = {
            cur: {'tx_fee': float(fee)} for cur, fee in self.api.withdraw_fees()['withdraw'].items()
        }
        self._fee = float(self.api.fees()[0]['taker_fees']) / 100

    def fee(self, base_currency: str, quote_currency: str) -> float:
        return self._fee
