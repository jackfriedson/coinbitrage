from coinbitrage import bitlogging
from coinbitrage.exchanges.wss import WampWebsocket

from .formatter import PoloniexWebsocketFormatter


log = bitlogging.getLogger(__name__)


class PoloniexWebsocketAdapter(WampWebsocket):
    formatter = PoloniexWebsocketFormatter()

    def __init__(self):
        super(PoloniexWebsocketAdapter, self).__init__(
            name='poloniex',
            url='wss://api.poloniex.com',
            host='api.poloniex.com',
            port=443,
            realm='realm1')
