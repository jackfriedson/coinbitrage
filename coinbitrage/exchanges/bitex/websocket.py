from typing import Callable, Dict
from queue import Queue

from coinbitrage.exchanges.interfaces import WebsocketInterface
from coinbitrage.settings import Defaults


class BitExWSSAdapter(WebsocketInterface):
    """Class for implementing WSS adapters using the BitEx library."""
    _formatters = {}

    class QueueWrapper(object):
        """Wrapper around the BitEx websocket's data queue that adds additional
        funcitonality such as filtering and formatting messages.
        """
        def __init__(self, queue: Queue, formatters: Dict[str, Callable]):
            self._queue = queue
            self._formatters = formatters
            self._allowed_channels = set()
            self._allowed_pairs = set()

        def __getattr__(self, name: str):
            return getattr(self._queue, name)

        def get(self):
            message = self._queue.get()
            formatter = self._formatters[message[0]]
            return formatter(message)

    def __init__(self, websocket, *args, **kwargs):
        self._websocket = None
        self.queue = None
        self._init_websocket(websocket)
        super(BitExWSSAdapter, self).__init__(*args, **kwargs)

    def _init_websocket(self, websocket):
        self._websocket = websocket
        queue_wrapper = self.QueueWrapper(self._websocket.data_q, self._formatters)
        self._websocket.data_q = queue_wrapper
        self.queue = self._websocket.data_q

    def subscribe(self,
                  base_currency: str,
                  channel: str = 'ticker',
                  quote_currency: str = Defaults.QUOTE_CURRENCY):
        if not self._websocket.running:
            self._websocket.start()

    def shutdown(self):
        self._websocket.stop()
