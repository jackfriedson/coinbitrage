import asyncio
import json
import logging
import traceback
from collections import namedtuple
from functools import partial
from queue import Queue
from threading import Event, RLock, Thread
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import txaio
from autobahn.asyncio.wamp import ApplicationSession, ApplicationSessionFactory
from autobahn.asyncio.websocket import WampWebSocketClientFactory, WampWebSocketClientProtocol
from autobahn.wamp.types import ComponentConfig
from websocket import WebSocketApp, WebSocketException, WebSocketTimeoutException, create_connection

from coinbitrage import bitlogging
from coinbitrage.exchanges.interfaces import WebsocketInterface
from coinbitrage.exchanges.order_book import OrderBook
from coinbitrage.utils import thread_running


log = bitlogging.getLogger(__name__)


WebsocketMessage = namedtuple('WebsocketMessage', ['channel', 'pair', 'data'])


class BaseWebsocket(WebsocketInterface):

    def __init__(self, name: Optional[str] = None, url: Optional[str] = None):
        self.name = name or self._name
        self.url = url or self._url
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
        if thread_running(self._websocket_thread):
            self._stop_websocket()
        self._channels.add(channel)
        self._pairs.add(self.formatter.pair(base_currency, quote_currency))
        self._start_websocket()

    def _start_controller(self):
        log.debug('Starting {exchange} controller thread...', event_data={'exchange': self.name},
                  event_name='websocket_adapter.controller.start')
        if thread_running(self._controller_thread):
            log.warning('Attempted to start the controller thread but it was already running',
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
            log.warning('Attemped to stop the controller thread but it wasn\'t running',
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
                log.warning('Attempted to start the websocket thread but it was already running',
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
                log.warning('Attempted to stop the websocket thread but it wasn\'t running',\
                            event_name='websocket_adapter.no_thread_to_stop_websocket')
                return
            self.websocket_running.clear()
            self._websocket_thread.join()
            self._websocket_thread = None

    def _websocket(self, *args):
        try:
            conn = create_connection(self.url)
        except WebSocketException as e:
            self._controller_queue.put('restart')
            return

        self._init_subscriptions(conn)

        while self.websocket_running.is_set():
            try:
                msg = json.loads(conn.recv())
            except WebSocketTimeoutException:
                self._controller_queue.put('restart')
                return

            msg = self.formatter.websocket_message(msg)

            if msg and msg.channel in self._channels and msg.pair in self._pairs:
                self.queue.put(msg)

    def _init_subscriptions(self, conn):
        for channel in self._channels:
            for pair in self._pairs:
                self._subscribe(conn, channel, pair)

    def _subscribe(self, connection, channel: str, pair: str):
        raise NotImplementedError


class WebsocketOrderBook(BaseWebsocket):

    def __init__(self, order_book,  *args, **kwargs):
        super(WebsocketOrderBook, self).__init__(*args, **kwargs)
        self._book = order_book
        self._ws = None

    def _websocket(self, *args):
        self._ws = WebSocketApp(self.url,
                                on_open=self._init_subscriptions,
                                on_message=self._on_message,
                                on_error=self._on_error)
        self._ws.run_forever()

    def _stop_websocket(self):
        log.debug('Stopping {exchange} websocket thread...', event_data={'exchange': self.name},
                  event_name='websocket_adapter.websocket.stop')
        self.websocket_running.clear()
        with self._lock:
            if self._ws:
                self._ws.close()
                self._ws = None
            if thread_running(self._websocket_thread):
                self._websocket_thread.join()
            self._websocket_thread = None
            self._book.clear()

    def _on_message(self, ws, message):
        msg = self.formatter.websocket_message(json.loads(message))
        if msg and msg.channel == 'order_book':
            try:
                self._book.update(msg.data)
            except OrderBookUpdateError:
                ws.close()

    def _on_error(self, ws, error):
        log.warning('{exchange} order book encountered an error: {error}, restarting thread...',
                    event_name='websocket.error',
                    event_data={'exchange': self.name, 'error': error})
        self._controller_queue.put('restart')
        ws.close()


class WampWebsocket(BaseWebsocket):

    def __init__(self, name: str, url: str, host: str, port: int, realm: str, ssl: bool = True):
        super(WampWebsocket, self).__init__(name, url)
        self.realm = realm
        self.host = host
        self.port = port
        self.ssl = ssl
        self._websocket_loop = None

    def _start_websocket(self):
        self._websocket_loop = asyncio.new_event_loop()
        super(WampWebsocket, self)._start_websocket()

    def _stop_websocket(self):
        if self._websocket_loop:
            self._websocket_loop.stop()
        super(WampWebsocket, self)._stop_websocket()

    def _websocket(self, *args):
        loop = self._websocket_loop
        asyncio.set_event_loop(loop)
        txaio.config.loop = loop
        session_factory = ApplicationSessionFactory(ComponentConfig(realm=self.realm))
        session_factory.session = partial(WampComponent, self.queue, self._channels, self._pairs, self.formatter)
        protocol_factory = WampWebSocketClientFactory(session_factory, url=self.url)
        protocol_factory.protocol = partial(WampProtocol, self._controller_queue)
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
    def __init__(self, websocket_queue: Queue, channels: List[str], pairs: List[str], formatter, *args, **kwargs):
        super(WampComponent, self).__init__(*args, **kwargs)
        self._queue = websocket_queue
        self._channels = channels
        self._pairs = pairs
        self.formatter = formatter

    async def onJoin(self, details):
        for channel in self._channels:
            def callback_fn(*args):
                data = getattr(self.formatter, channel)(args)
                self._queue.put(data)

            await self.subscribe(callback_fn, channel)
