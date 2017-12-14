import logging
from functools import partial
from queue import Queue
from threading import Event, RLock, Thread
from typing import Callable, Dict, List

import asyncio
import txaio
from autobahn.asyncio.wamp import ApplicationSession, ApplicationSessionFactory
from autobahn.asyncio.websocket import WampWebSocketClientFactory, WampWebSocketClientProtocol
from autobahn.wamp.types import ComponentConfig

from coinbitrage import bitlogging
from coinbitrage.exchanges.interfaces import WebsocketInterface
from coinbitrage.utils import thread_running


log = bitlogging.getLogger(__name__)


class BaseWebsocketAdapter(WebsocketInterface):

    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url
        self.queue = Queue()
        self.controller_running = Event()
        self.websocket_running = Event()
        self._pairs = set()
        self._channels = set()

        self._lock = RLock()
        self._controller_queue = Queue()
        self._controller_thread = None
        self._websocket_thread = None

    @property
    def running(self):
        return thread_running(self._websocket_thread)

    def subscribe(self,
                  pair: str,
                  channel: str = 'ticker'):
        if not thread_running(self._controller_thread):
            self._start_controller()

        self._pairs.add(pair)
        self._channels.add(channel)

        command = 'start' if not thread_running(self._websocket_thread) else 'restart'
        self._controller_queue.put(command)

    def _start_controller(self):
        log.debug('Starting {exchange} controller thread...', event_data={'exchange': self.name},
                  event_name='websocket_adapter.controller.start')
        if thread_running(self._controller_thread):
            log.warning('Attempted to start a thread but it was already running',
                        event_name='websocket_adapter.thread_already_running')
            return
        self.controller_running.set()
        self._controller_thread = Thread(target=self._controller, daemon=True,
                                         name='{}ControllerThread'.format(self.name.title()))
        self._controller_thread.start()

    def _stop_controller(self):
        log.debug('Stopping {exchange} controller thread...', event_data={'exchange': self.name},
                  event_name='websocket_adapter.controller.stop')
        if not thread_running(self._controller_thread):
            log.warning('Attemped to stop a thread but there was none running',
                        event_name='websocket_adapter.no_thread_to_stop')
            return
        self.controller_running.clear()
        self._controller_thread.join()

    def _controller(self):
        while self.controller_running.is_set():
            if not self._controller_queue.empty():
                command = self._controller_queue.get()
                args = []
                if isinstance(command, tuple):
                    args.extend(command[1:])
                    command = command[0]
                self._eval_command(command, *args)

    def _eval_command(self, command: str, *args):
        if command == 'start':
            self._start(*args)
        elif command == 'stop':
            self._stop()
        elif command == 'restart':
            with self._lock:
                self._stop()
                self._start(*args)

    def _start(self, *args):
        log.debug('Starting {exchange} websocket thread...', event_data={'exchange': self.name},
                  event_name='websocket_adapter.websocket.start')
        with self._lock:
            if thread_running(self._websocket_thread):
                log.warning('Attempted to start a thread but it was already running',
                            event_name='websocket_adapter.thread_already_running')
                return
            self.websocket_running.set()
            self._websocket_thread = Thread(target=self._websocket, args=args, daemon=True,
                                            name='{}WebsocketThread'.format(self.name.title()))
            self._websocket_thread.start()

    def _stop(self):
        log.debug('Stopping {exchange} websocket thread...', event_data={'exchange': self.name},
                  event_name='websocket_adapter.websocket.stop')
        with self._lock:
            if not thread_running(self._websocket_thread):
                log.warning('Attempted to stop a thread but there was none running',\
                            event_name='websocket_adapter.no_thread_to_stop')
                return
            self.websocket_running.clear()
            self._websocket_thread.join()
            self._websocket_thread = None

    def _websocket(self, *args):
        raise NotImplementedError

    def shutdown(self):
        self._stop_controller()
        self._stop()


class WampWebsocketAdapter(BaseWebsocketAdapter):

    _formatters = {}

    def __init__(self, name: str, url: str, host: str, port: int, realm: str,
                 ssl: bool = True):
        super(WampWebsocketAdapter, self).__init__(name, url)
        self.realm = realm
        self.host = host
        self.port = port
        self._websocket_loop = None

    def _start(self):
        self._websocket_loop = asyncio.new_event_loop()
        super(WampWebsocketAdapter, self)._start()

    def _stop(self):
        self._websocket_loop.stop()
        super(WampWebsocketAdapter, self)._stop()

    def _websocket(self, *args):
        loop = self._websocket_loop
        asyncio.set_event_loop(loop)
        txaio.config.loop = loop
        session_factory = ApplicationSessionFactory(ComponentConfig(realm=self.realm))
        session_factory.session = partial(WampComponent, self.queue, self._channels, self._formatters)
        protocol_factory = WampWebSocketClientFactory(session_factory, url=self.url)
        protocol_factory.protocol = partial(WampProtocol, self._controller_queue)
        protocol_factory.setProtocolOptions(openHandshakeTimeout=60., closeHandshakeTimeout=60.)
        coro = loop.create_connection(protocol_factory, self.host, self.port, ssl=True)
        transport, protocol = loop.run_until_complete(coro)
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass
        if protocol._session:
            loop.run_until_complete(protocol._session.leave())
        loop.close()


class WampProtocol(WampWebSocketClientProtocol):

    def __init__(self, controller_queue, *args, **kwargs):
        self._queue = controller_queue
        super(WampProtocol, self).__init__(*args, **kwargs)

    def onClose(self, wasClean: bool, code: int, reason: str):
        asyncio.get_event_loop().stop()
        if not wasClean:
            log.info('Disconnected uncleanly, retrying...')
            self._queue.put('restart')
        super(WampProtocol, self).onClose(wasClean, code, reason)


class WampComponent(ApplicationSession):
    def __init__(self, queue: Queue, channels: List[str], pair: str,
                 formatters: Dict[str, Callable], *args, **kwargs):
        super(WampComponent, self).__init__(*args, **kwargs)
        self._queue = queue
        self._channels = channels
        self._pair = pair
        self._formatters = formatters

    async def onJoin(self, details):
        for channel in self._channels:
            def callback_fn(*args):
                data = self._formatters[channel](args)
                self._queue.put(data)
            await self.subscribe(callback_fn, channel)
