from coinbitrage import bitlogging
from coinbitrage.exchanges.wss import WampWebsocketAdapter

from .formatter import PoloniexWebsocketFormatter


log = bitlogging.getLogger(__name__)


class PoloniexWebsocketAdapter(WampWebsocketAdapter):
    formatter = PoloniexWebsocketFormatter()

    def __init__(self):
        super(PoloniexWebsocketAdapter, self).__init__(
            name='poloniex',
            url='wss://api.poloniex.com',
            host='api.poloniex.com',
            port=443,
            realm='realm1')
