from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.mixins import WebsocketMixin

from .api import CoinbaseAPIAdapter
from .websocket import CoinbaseWebsocket


class CoinbaseClient(BaseExchangeClient, WebsocketMixin):
    name = 'coinbase'
    _api_class = CoinbaseAPIAdapter

    def __init__(self, coinbase_key_file: str, gdax_key_file: str = None):
        BaseExchangeClient.__init__(self, coinbase_key_file, gdax_key_file=gdax_key_file)
        WebsocketMixin.__init__(self, CoinbaseWebsocket())
