from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.mixins import WebsocketMixin

from .api import BitfinexAPIAdapter
from .websocket import BitfinexWebsocketAdapter


class BitfinexClient(BaseExchangeClient, WebsocketMixin):
    _api_class = BitfinexAPIAdapter
    _websocket_class = BitfinexWebsocketAdapter
    name = 'bitfinex'
    max_refresh_delay = 10

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        WebsocketMixin.__init__(self)

    def init(self):
        self.supported_pairs = self.api.pairs()
        self.currency_info = {
            cur: {'tx_fee': float(fee)} for cur, fee in self.api.withdraw_fees()['withdraw'].items()
        }
        self._fee = float(self.api.fees()[0]['taker_fees']) / 100

    def fee(self, base_currency: str, quote_currency: str) -> float:
        return self._fee
