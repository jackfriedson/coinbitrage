
from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.mixins import PeriodicRefreshMixin

from .api import BittrexAPIAdapter


class BittrexClient(BaseExchangeClient, PeriodicRefreshMixin):
    name = 'bittrex'
    _api_class = BittrexAPIAdapter

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        PeriodicRefreshMixin.__init__(self, refresh_interval=1)
        self.currency_info = self.api.currencies()
        self.supported_pairs = self.api.pairs()
