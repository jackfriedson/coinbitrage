
from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.mixins import PeriodicRefreshMixin

from .api import PoloniexAPIAdapter


class PoloniexClient(BaseExchangeClient, PeriodicRefreshMixin):
    name = 'poloniex'
    _api_class = PoloniexAPIAdapter

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        PeriodicRefreshMixin.__init__(self, 1)
