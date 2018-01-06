from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.mixins import PeriodicRefreshMixin

from .api import BitfinexAPIAdapter


class BitfinexClient(BaseExchangeClient, PeriodicRefreshMixin):
    name = 'bitfinex'
    _api_class = BitfinexAPIAdapter

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        PeriodicRefreshMixin.__init__(self, 1)

    def init(self):
        raise NotImplementedError
