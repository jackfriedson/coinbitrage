from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.mixins import WebsocketOrderBookMixin

from .api import BitfinexAPIAdapter
from .websocket import BitfinexWebsocketOrderBook


class BitfinexClient(BaseExchangeClient, WebsocketOrderBookMixin):
    _api_class = BitfinexAPIAdapter
    _websocket_order_book_class = BitfinexWebsocketOrderBook
    max_refresh_delay = 10
    name = 'bitfinex'

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        WebsocketOrderBookMixin.__init__(self)

    def init(self):
        self.supported_pairs = self.api.pairs()
        self.currency_info = {
            cur: {'tx_fee': float(fee)} for cur, fee in self.api.withdraw_fees()['withdraw'].items()
        }
        self._fee = float(self.api.fees()[0]['taker_fees']) / 100

    def fee(self, base_currency: str, quote_currency: str) -> float:
        return self._fee
