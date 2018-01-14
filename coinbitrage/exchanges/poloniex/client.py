
from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.mixins import PeriodicRefreshMixin, WebsocketTickerMixin

from .api import PoloniexAPIAdapter
from .websocket import PoloniexWebsocketAdapter


class PoloniexClient(BaseExchangeClient, WebsocketTickerMixin):
    _api_class = PoloniexAPIAdapter
    _websocket_class = PoloniexWebsocketAdapter
    max_refresh_delay = 10
    name = 'poloniex'

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        WebsocketTickerMixin.__init__(self)

    def init(self):
        self.currency_info = self.api.currencies()
        self.supported_pairs = self.api.pairs()
        self._fee = float(self.api.fees()['takerFee'])

    def fee(self, base_currency: str, quote_currency: str) -> float:
        return self._fee
