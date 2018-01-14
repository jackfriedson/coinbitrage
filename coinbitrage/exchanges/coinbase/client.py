from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.mixins import PeriodicRefreshMixin

from .api import CoinbaseAPIAdapter
from .websocket import CoinbaseWebsocket


class CoinbaseClient(BaseExchangeClient, PeriodicRefreshMixin):
    _api_class = CoinbaseAPIAdapter
    _fees = {
        'BTC': 0.0025,
        'ETH': 0.003,
        'LTC': 0.003
    }
    name = 'coinbase'

    def __init__(self, coinbase_key_file: str, gdax_key_file: str = None):
        BaseExchangeClient.__init__(self, coinbase_key_file, gdax_key_file=gdax_key_file)
        PeriodicRefreshMixin.__init__(self, refresh_interval=1)

    def init(self):
        self.supported_pairs = self.api.pairs()

    def fee(self, base_currency: str, quote_currency: str) -> float:
        return self._fees[base_currency]
