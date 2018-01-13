from bitex.api.WSS import BitfinexWSS

from coinbitrage.exchanges.bitex import BitExWebsocketAdapter

from .formatter import BitfinexWebsocketFormatter


class BitfinexWebsocketAdapter(BitExWebsocketAdapter):
    formatter = BitfinexWebsocketFormatter()
    _websocket_class = BitfinexWSS
