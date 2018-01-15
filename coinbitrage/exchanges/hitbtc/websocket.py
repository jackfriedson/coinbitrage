import time
import json

from bitex.api.WSS import HitBTCWSS
from websocket import WebSocketTimeoutException, create_connection

from coinbitrage.exchanges.wss import BaseWebsocket, WebsocketOrderBook

from .formatter import HitBtcWebsocketFormatter


class HitBtcWebsocketMixin(object):
    _name = 'hitbtc'
    _url = 'wss://api.hitbtc.com/api/2/ws'
    formatter = HitBtcWebsocketFormatter()

    def _subscribe(self, conn, channel: str, pair: str):
        if channel == 'ticker':
            msg = {
                'method': 'subscribeTicker',
                'params': {'symbol': pair},
                'id': time.time(),
            }
        elif channel == 'order_book':
            msg = {
                'method': 'subscribeOrderbook',
                'params': {'symbol': pair},
                'id': time.time(),
            }
        else:
            raise NotImplementedError('Channel {} is not implemented for HitBTC'.format(channel))

        conn.send(json.dumps(msg))


class HitBtcWebsocketAdapter(HitBtcWebsocketMixin, BaseWebsocket):
    pass


class HitBtcWebsocketOrderBook(HitBtcWebsocketMixin, WebsocketOrderBook):
    pass
