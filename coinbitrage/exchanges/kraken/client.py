from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.mixins import PeriodicRefreshMixin

from .api import KrakenTetherAdapter


class KrakenClient(BaseExchangeClient, PeriodicRefreshMixin):
    name = 'kraken'
    _api_class = KrakenTetherAdapter

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        PeriodicRefreshMixin.__init__(self, refresh_interval=1)
