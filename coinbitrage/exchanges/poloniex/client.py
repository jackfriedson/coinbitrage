
from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.mixins import PeriodicRefreshMixin

from .api import PoloniexAPIAdapter


class PoloniexClient(BaseExchangeClient, PeriodicRefreshMixin):
    name = 'poloniex'
    _api_class = PoloniexAPIAdapter

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        PeriodicRefreshMixin.__init__(self, 1)

    def init(self):
        self.currency_info = self.api.currencies()
        self.supported_pairs = self.api.pairs()
        self._fee = float(self.api.fees()['takerFee'])

    def fee(self, base_currency: str, quote_currency: str) -> float:
        return self._fee