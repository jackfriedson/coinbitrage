import asyncio
import logging
from functools import partial
from queue import Queue
from threading import Event, RLock, Thread
from typing import Callable, Dict, List

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

    def start(self):
        self._start_controller()

    def stop(self):
        self._stop_controller()
        self._stop_websocket()

    def subscribe(self,
                  channel: str,
                  base_currency: str,
                  quote_currency: str):
        self._pairs.add(self.formatter.pair(base_currency, quote_currency))
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
            self._start_websocket(*args)
        elif command == 'stop':
            self._stop_websocket()
        elif command == 'restart':
            with self._lock:
                self._stop_websocket()
                self._start_websocket(*args)

    def _start_websocket(self, *args):
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

    def _stop_websocket(self):
        log.debug('Stopping {exchange} websocket thread...', event_data={'exchange': self.name},
                  event_name='websocket_adapter.websocket.stop')
        with self._lock:
            if not thread_running(self._websocket_thread):
                log.warning('Attempted to stop a thread but there was none running',\
                            event_name='websocket_adapter.no_thread_to_stop_websocket')
                return
            self.websocket_running.clear()
            self._websocket_thread.join()
            self._websocket_thread = None

    def _websocket(self, *args):
        raise NotImplementedError


class WampWebsocketAdapter(BaseWebsocketAdapter):

    def __init__(self, name: str, url: str, host: str, port: int, realm: str, ssl: bool = True):
        super(WampWebsocketAdapter, self).__init__(name, url)
        self.realm = realm
        self.host = host
        self.port = port
        self.ssl = ssl
        self._websocket_loop = None

    def _start_websocket(self):
        self._websocket_loop = asyncio.new_event_loop()
        super(WampWebsocketAdapter, self)._start_websocket()

    def _stop_websocket(self):
        if self._websocket_loop:
            self._websocket_loop.stop()
        super(WampWebsocketAdapter, self)._stop_websocket()

    def _websocket(self, *args):
        loop = self._websocket_loop
        asyncio.set_event_loop(loop)
        txaio.config.loop = loop
        session_factory = ApplicationSessionFactory(ComponentConfig(realm=self.realm))
        session_factory.session = partial(WampComponent,
                                          websocket_queue=self.queue,
                                          channels=self._channels,
                                          pairs=self._pairs,
                                          formatter=self.formatter)
        protocol_factory = WampWebSocketClientFactory(session_factory, url=self.url)
        protocol_factory.protocol = partial(WampProtocol, controller_queue=self._controller_queue)
        protocol_factory.setProtocolOptions(openHandshakeTimeout=60., closeHandshakeTimeout=60.)
        coro = loop.create_connection(protocol_factory, self.host, self.port, ssl=self.ssl)
        _, protocol = loop.run_until_complete(coro)

        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass
        if protocol._session:
            loop.run_until_complete(protocol._session.leave())
        loop.close()


class WampProtocol(WampWebSocketClientProtocol):

    def __init__(self, *args, controller_queue = None, **kwargs):
        self._queue = controller_queue
        super(WampProtocol, self).__init__(*args, **kwargs)

    def onClose(self, wasClean: bool, code: int, reason: str):
        asyncio.get_event_loop().stop()
        if not wasClean:
            log.info('Disconnected uncleanly, retrying...')
            self._queue.put('restart')
        super(WampProtocol, self).onClose(wasClean, code, reason)


class WampComponent(ApplicationSession):
    def __init__(self, *args,
                 websocket_queue: Queue = None,
                 channels: List[str] = None,
                 pairs: List[str] = None,
                 formatter = None,
                 **kwargs):
        super(WampComponent, self).__init__(*args, **kwargs)
        self._queue = websocket_queue
        self._channels = channels
        self._pairs = pairs
        self.formatter = formatter

    async def onJoin(self, details):
        log.debug('joining session...')
        for channel in self._channels:
            log.debug('subscribing to {}...'.format(channel))

            def callback_fn(*args):
                data = getattr(self.formatter, channel)(args)
                self._queue.put(data)

            await self.subscribe(callback_fn, channel)
