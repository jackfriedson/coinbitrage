import time
import json

from bitex.api.WSS import HitBTCWSS
from websocket import WebSocketTimeoutException, create_connection

from coinbitrage.exchanges.wss import BaseWebsocket

from .formatter import HitBtcWebsocketFormatter


class HitBtcWebsocketAdapter(BaseWebsocket):
    formatter = HitBtcWebsocketFormatter()

    def __init__(self):
        super(HitBtcWebsocketAdapter, self).__init__('hitbtc', 'wss://api.hitbtc.com/api/2/ws')

    def _subscribe(self, conn, channel: str, pair: str):
        if channel == 'ticker':
            msg = {
                'method': 'subscribeTicker',
                'params': {'symbol': pair},
                'id': time.time()
            }
        else:
            raise NotImplementedError

        conn.send(json.dumps(msg))
