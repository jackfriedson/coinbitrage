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

    def _websocket(self):
        try:
            conn = create_connection(self.url)
        except Exception:
            self._controller_queue.put('restart')
            return

        for channel in self._channels:
            for pair in self._pairs:
                self._subscribe(conn, channel, pair)

        while self.websocket_running.is_set():
            try:
                msg = conn.recv()
                msg = json.loads(msg)
            except WebSocketTimeoutException:
                self._controller_queue.put('restart')
                return

            method = msg.get('method')
            if method:
                data = msg['params']
                formatter = getattr(self.formatter, method)
                self.queue.put((data['symbol'], formatter(data)))

        conn.close()

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
