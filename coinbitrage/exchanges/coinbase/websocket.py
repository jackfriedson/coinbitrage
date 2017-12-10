import json
import time

from websocket import create_connection, WebSocketTimeoutException, WebSocketConnectionClosedException

from coinbitrage import bitlogging
from coinbitrage.exchanges.wss import BaseWebsocketAdapter


log = bitlogging.getLogger(__name__)


WEBSOCKET_TIMEOUT = 30.


class CoinbaseWebsocket(BaseWebsocketAdapter):
    _formatters = {
        'ticker': lambda msg: {
            'bid': float(msg[1]['best_bid']),
            'ask': float(msg[1]['best_ask']),
            'time': msg[2],
        }
    }

    def __init__(self):
        super(CoinbaseWebsocket, self).__init__('coinbase', 'wss://ws-feed.gdax.com')

    def _websocket(self, *args):
        connection = create_connection(self.url, timeout=WEBSOCKET_TIMEOUT)
        payload = {
            'type': 'subscribe',
            'product_ids': list(self._pairs),
            'channels': list(self._channels)
        }
        connection.send(json.dumps(payload))
        while self.websocket_running.is_set():
            try:
                data = json.loads(connection.recv())
            except (WebSocketTimeoutException, WebSocketConnectionClosedException,
                    ConnectionResetError) as e:
                log.warning('Websocket connection error: {exception}; Restarting...',
                            event_name='coinbase_websocket.connection_error',
                            event_data={'exception': e})
                self._controller_queue.put('restart')
            else:
                if 'product_id' in data:
                    data_tuple = (data['product_id'], data, time.time())
                    formatted = self._formatters[data['type']](data_tuple)
                    self.queue.put(formatted)
