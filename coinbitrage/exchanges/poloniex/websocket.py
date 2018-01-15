import json

from websocket import WebSocketException, WebSocketTimeoutException, create_connection

from coinbitrage import bitlogging
from coinbitrage.exchanges.wss import BaseWebsocket, WebsocketOrderBook

from .formatter import PoloniexWebsocketFormatter


log = bitlogging.getLogger(__name__)


class PoloniexWebsocketMixin(object):
    _name = 'poloniex'
    _url = 'wss://api2.poloniex.com/'
    formatter = PoloniexWebsocketFormatter()

    def _subscribe(self, conn, channel: str, pair: str):
        channel = self.formatter.get_channel_id(channel, pair)
        conn.send(json.dumps({ 'command': 'subscribe', 'channel': channel}))


class PoloniexWebsocketAdapter(PoloniexWebsocketMixin, BaseWebsocket):
    pass


class PoloniexWebsocketOrderBook(PoloniexWebsocketMixin, WebsocketOrderBook):
    pass
