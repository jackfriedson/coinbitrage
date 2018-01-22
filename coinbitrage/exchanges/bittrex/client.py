from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.mixins import RefreshOrderBookMixin

from .api import BittrexAPIAdapter


class BittrexClient(BaseExchangeClient, RefreshOrderBookMixin):
    _api_class = BittrexAPIAdapter
    name = 'bittrex'

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        RefreshOrderBookMixin.__init__(self, refresh_interval=1)

    def init(self):
        self.currency_info = self.api.currencies()
        self.supported_pairs = self.api.pairs()
