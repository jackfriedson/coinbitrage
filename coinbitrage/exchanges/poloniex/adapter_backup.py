import asyncio
import logging
import time
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from threading import Thread
from typing import Callable, List, Optional
from queue import Queue

import txaio
from bitex import Poloniex
from autobahn.asyncio.wamp import ApplicationSession, ApplicationSessionFactory
from autobahn.asyncio.websocket import WampWebSocketClientFactory, WampWebSocketClientProtocol
from autobahn.wamp.types import ComponentConfig

from coinbitrage import settings
from coinbitrage.exchanges.bitex.adapter import BitExRESTAdapter


log = bitlogging.getLogger(__name__)


class PoloniexAPIAdapter(BitExRESTAdapter):
    _formatters = {
        'ticker': lambda msg: {
            'pair': msg[0],
            'bid': float(msg[3]),
            'ask': float(msg[2])
        }
    }

    def __init__(self, key_file: str):
        super(PoloniexAPIAdapter, self).__init__(api=Poloniex(key_file=key_file))
        self._fee = None
        self.queue = Queue()

        self._controller_queue = Queue()
        self._controller_thread = None
        self._wamp_thread = None

    def fee(self,
            base_currency: str,
            quote_currency: str = settings.DEFAULT_QUOTE_CURRENCY,
            use_cached: bool = True) -> float:
        if not self._fee or not use_cached:
            self._fee = float(self._api.fees().json()['takerFee'])
        return self._fee

    def get_deposit_address(self, currency: str) -> str:
        all_addresses = super(PoloniexAPIAdapter, self).get_deposit_address(currency)
        if currency in all_addresses:
            return all_addresses[currency]
        return self._generate_new_address(currency)

    def _generate_new_address(self, currency: str) -> str:
        params = {'currency': currency, 'command': 'generateNewAddress'}
        response = self._api.private_query('tradingApi', params=params)
        return response.json()['response']

    def subscribe(self,
                  base_currency: str,
                  channel: str = 'ticker',
                  quote_currency: str = settings.DEFAULT_QUOTE_CURRENCY):
        if not self._controller_thread or not self._controller_thread.is_alive():
            self._controller_thread = Thread(self._controller, daemon=True,
                                             name='Poloniex-Controller-Thread')
            self._controller_thread.start()

        pair = self.currency_pair(base_currency, quote_currency)
        formatter = self._formatters[channel]

        config = ComponentConfig(realm='realm1')
        session_factory = ApplicationSessionFactory(config)
        session_factory.session = partial(_PoloniexWAMPComponent, self.queue, channel, pair, formatter)

        self._wamp_thread = Thread(target=self._wamp, args=(session_factory,),
                                   daemon=True, name='Poloniex-Data-Thread')
        self._wamp_thread.start()

    def close(self):
        self._wamp_thread.join()
        self._wamp_thread = None

    def _wamp(self, session_factory):
        print('Starting thread...')
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        txaio.config.loop = loop
        protocol_factory = WampWebSocketClientFactory(session_factory, url='wss://api.poloniex.com')
        protocol_factory.protocol = _CustomWampWebSocketProtocol
        protocol_factory.setProtocolOptions(openHandshakeTimeout=60.)
        coro = loop.create_connection(protocol_factory, 'api.poloniex.com', 443, ssl=True)
        try:
            transport, protocol = loop.run_until_complete(coro)
            # protocol.is_closed.add_done_callback(lambda x: print('Future: ', x.result()))
            loop.run_forever()
        except Exception as e:
            log.debug('Caught an exception while running thread, closing loop', exc_info=True)
        finally:
            print('closing...')
            loop.close()

        print('Thread ending...')

    @staticmethod
    def currency_pair(base_currency: str, quote_currency: str) -> str:
        # Poloniex only has Tether exchanges, not USD
        if quote_currency == 'USD':
            quote_currency = 'USDT'

        return quote_currency + '_' + base_currency


class _RetryOnUncleanDisconnectProtocol(WampWebSocketClientProtocol):

    def __init__(self, ):
        pass

    def onOpen(self):
        super

    def onClose(self, wasClean, code, reason):
        print('closing protocol...')
        if not wasClean:

        super(_RetryProtocol, self).onClose(wasClean, code, reason)


class _PoloniexWAMPComponent(ApplicationSession):

    def __init__(self, queue: Queue, channel: str, pair: str,
                 formatter: Callable, *args, **kwargs):
        self._queue = queue
        self._channel = channel
        self._pair = pair
        self._formatter = formatter
        super(_PoloniexWAMPComponent, self).__init__(*args, **kwargs)
        print('initializing...')

    def onOpen(self, *args, **kwargs):
        print('opening session...')
        super(_PoloniexWAMPComponent, self).onOpen(*args, **kwargs)

    def onClose(self, *args, **kwargs):
        print('closing session...')
        super(_PoloniexWAMPComponent, self).onClose(*args, **kwargs)

    async def onJoin(self, details):
        print('joining...')

        def _callback_fn(*args):
            if self._channel == 'ticker' and self._pair != args[0]:
                return
            formatted = self._formatter(args)
            self._queue.put(formatted)

        await self.subscribe(_callback_fn, self._channel)

    def onDisconnect(self):
        asyncio.get_event_loop().stop()
