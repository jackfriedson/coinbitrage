import json

from websocket import WebSocketException, WebSocketTimeoutException, create_connection

from coinbitrage import bitlogging
from coinbitrage.exchanges.wss import BaseWebsocket

from .formatter import PoloniexWebsocketFormatter


log = bitlogging.getLogger(__name__)


class PoloniexWebsocketAdapter(BaseWebsocket):
    formatter = PoloniexWebsocketFormatter()

    def __init__(self):
        super(PoloniexWebsocketAdapter, self).__init__('poloniex', 'wss://api2.poloniex.com/')

    def _subscribe(self, conn, channel: str, pair: str):
        channel = self.formatter.get_channel_id(channel, pair)
        conn.send(json.dumps({ 'command': 'subscribe', 'channel': channel}))
