import logging
import time
from abc import ABC, abstractproperty
from threading import Event, RLock, Thread
from typing import Dict

from requests.exceptions import RequestException

from coinbitrage import bitlogging
from coinbitrage.exchanges.utils import thread_running
from coinbitrage.settings import DEFAULT_QUOTE_CURRENCY


log = bitlogging.getLogger(__name__)


def format_bid_ask(bid_ask: Dict[str, float]) -> Dict[str, str]:
    return {
        k: '{:.6f}'.format(v) for k, v in bid_ask.items()
    }


class LiveUpdateMixin(ABC):

    def initialize(self,
                   base_currency: str,
                   quote_currency: str = DEFAULT_QUOTE_CURRENCY):
        pass

    def shutdown(self):
        pass


class WebsocketMixin(LiveUpdateMixin):

    def __init__(self, websocket, *args, **kwargs):
        self._websocket = websocket
        self._bid_ask = {'bid': None, 'ask': None, 'time': None}
        super(WebsocketMixin, self).__init__(*args, **kwargs)

    def initialize(self,
                   base_currency: str,
                   quote_currency: str = DEFAULT_QUOTE_CURRENCY):
        self._websocket.subscribe(self.pair(base_currency, quote_currency))

    def shutdown(self):
        self._websocket.shutdown()

    def _update(self):
        bid_ask = None
        while not self._websocket.queue.empty():
            bid_ask = self._websocket.queue.get()
        if bid_ask:
            log.debug('{exchange} {bid_ask}', event_name='websocket_mixin.update',
                      event_data={'exchange': self.name, 'bid_ask': format_bid_ask(bid_ask)})
            self._bid_ask = bid_ask

    def bid_ask(self,
            base_currency: str,
            quote_currency: str = DEFAULT_QUOTE_CURRENCY):
        self._update()
        return self._bid_ask


class PeriodicRefreshMixin(LiveUpdateMixin):

    def __init__(self, refresh_interval, *args, **kwargs):
        self._interval = refresh_interval
        self._running = Event()
        self._lock = RLock()
        self._refresh_thread = None
        self._bid_ask = {'bid': None, 'ask': None, 'time': None}
        super(PeriodicRefreshMixin, self).__init__(*args, **kwargs)

    def initialize(self,
                   base_currency: str,
                   quote_currency: str = DEFAULT_QUOTE_CURRENCY):
        if not thread_running(self._refresh_thread):
            self._base = base_currency
            self._quote = quote_currency
            self._running.set()
            self._refresh_thread = Thread(target=self._refresh, daemon=True,
                                          name='{}-refresh-thread'.format(self.name))
            self._refresh_thread.start()

    def shutdown(self):
        if thread_running(self._refresh_thread):
            self._running.clear()
            self._refresh_thread.join()
            self._refresh_thread = None

    def _refresh(self):
        while self._running.is_set():
            pair = self.pair(self._base, self._quote)
            try:
                ticker = self.ticker(self._base, quote_currency=self._quote)
            except RequestException as e:
                log.warning('Exception while connecting to {exchange}: {exc}',
                            event_name='refresh_mixin.request_error',
                            event_data={'exchange': self.name, 'exc': e})
            else:
                bid_ask = {
                    'bid': ticker.get('bid'),
                    'ask': ticker.get('ask'),
                    'time': ticker.get('time', time.time())
                }
                with self._lock:
                    self._bid_ask = bid_ask
                    log.debug('{exchange} {bid_ask}', event_name='refresh_mixin.update',
                              event_data={'exchange': self.name, 'bid_ask': format_bid_ask(self._bid_ask)})
            time.sleep(self._interval)

    def bid_ask(self,
                base_currency: str,
                quote_currency: str = DEFAULT_QUOTE_CURRENCY):
        with self._lock:
            # TODO: do we actually need to acquire the lock here?
            # should we be creating a copy of the dict instead of passing a reference?
            return self._bid_ask


class SeparateTradingAccountMixin(object):

    def bank_balance(self) -> Dict[str, float]:
        raise NotImplementedError

    def _transfer_between_accounts(self, to_trading: bool, currency: str, amount: float):
        raise NotImplementedError

    def bank_to_trading(self, currency: str, amount: float) -> bool:
        log.info('Transferring {amount} {currency} from {exchange} bank to trading account',
                 event_name='exchange_api.transfer.bank_to_trading',
                 event_data={'amount': amount, 'currency': currency, 'exchange': self.name})
        return self._transfer_between_accounts(True, currency, amount)

    def trading_to_bank(self, currency: str, amount: float) -> bool:
        log.info('Transferring {amount} {currency} from {exchange} trading account to bank',
                 event_name='exchange_api.transfer.trading_to_bank',
                 event_data={'amount': amount, 'currency': currency, 'exchange': self.name})
        return self._transfer_between_accounts(False, currency, amount)
