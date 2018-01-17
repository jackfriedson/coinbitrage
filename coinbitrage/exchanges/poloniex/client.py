
from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.mixins import PeriodicRefreshMixin, WebsocketOrderBookMixin

from .api import PoloniexAPIAdapter
from .websocket import PoloniexWebsocketOrderBook


class PoloniexClient(BaseExchangeClient, WebsocketOrderBookMixin):
    _api_class = PoloniexAPIAdapter
    _websocket_order_book_class = PoloniexWebsocketOrderBook
    name = 'poloniex'

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        WebsocketOrderBookMixin.__init__(self)

    def init(self):
        self.currency_info = self.api.currencies()
        self.supported_pairs = self.api.pairs()
        self._fee = float(self.api.fees()['takerFee'])

    def fee(self, base_currency: str, quote_currency: str) -> float:
        return self._fee
