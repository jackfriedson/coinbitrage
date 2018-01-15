import json

from bitex.api.WSS import BitfinexWSS

from coinbitrage.exchanges.bitex import BitExWebsocketAdapter
from coinbitrage.exchanges.wss import WebsocketOrderBook

from .formatter import BitfinexWebsocketFormatter


class BitfinexWebsocketAdapter(BitExWebsocketAdapter):
    _websocket_class = BitfinexWSS
    formatter = BitfinexWebsocketFormatter()


class BitfinexWebsocketOrderBook(WebsocketOrderBook):
    _name = 'bitfinex'
    _url = 'wss://api.bitfinex.com/ws/2'
    formatter = BitfinexWebsocketFormatter()

    def _subscribe(self, conn, channel: str, pair: str):
        msg = {
            'event': 'subscribe',
            'channel': self.formatter.hitbtc_channel_names[channel],
            'pair': pair
        }

        if channel == 'order_book':
            msg.update({
                'prec': 'P0',
                'freq': 'F0',
                'length': '100'
            })

        conn.send(json.dumps(msg))
