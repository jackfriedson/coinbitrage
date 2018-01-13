from typing import Callable, Dict, Optional
from queue import Queue

from coinbitrage.exchanges.interfaces import WebsocketInterface
from coinbitrage.settings import Defaults


class BitExWebsocketAdapter(WebsocketInterface):
    """Class for implementing WSS adapters using the BitEx library."""
    formatter = None
    _websocket_class = None

    class _QueueWrapper(object):
        """Wrapper around the BitEx websocket's data queue that can filter and format messages
        as needed.
        """
        def __init__(self, formatter: Dict[str, Callable]):
            self._queue = Queue()
            self._formatter = formatter
            self.allowed_channels = set()
            self.allowed_pairs = set()

        def __getattr__(self, name: str):
            return getattr(self._queue, name)

        def put(self, message: tuple, **kwargs):
            channel, pair, data = message
            data = getattr(self._formatter, channel)(data)
            self._queue.put((pair, data))

        def get(self, **kwargs):
            return self._queue.get(**kwargs)

    def __init__(self, *args, **kwargs):
        self._websocket = self._websocket_class()
        self.queue = self._websocket.data_q = self._QueueWrapper(self.formatter)
        super(BitExWebsocketAdapter, self).__init__(*args, **kwargs)

    def subscribe(self, channel: str, base_currency: str, quote_currency: str):
        subscribe_method = getattr(self._websocket, channel)
        subscribe_method(self.formatter.pair(base_currency, quote_currency))

    def start(self):
        self._websocket.start()

    def stop(self):
        self._websocket.stop()
