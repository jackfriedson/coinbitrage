import logging
import time
from abc import ABC, abstractproperty
from collections import defaultdict
from functools import partial, wraps
from threading import Event, RLock, Thread
from typing import Dict, List, Optional, Union

from requests.exceptions import RequestException

from coinbitrage import bitlogging
from coinbitrage.settings import Defaults
from coinbitrage.utils import thread_running


log = bitlogging.getLogger(__name__)


def format_bid_ask(bid_ask: Dict[str, float]) -> Dict[str, str]:
    return {k: '{:.6f}'.format(v) for k, v in bid_ask.items()}


class LiveUpdateMixin(object):

    def start_live_updates(self,
                           base_currency: Union[str, List[str]],
                           quote_currency: str = Defaults.QUOTE_CURRENCY):
        raise NotImplementedError

    def stop_live_updates(self):
        raise NotImplementedError

    def bid_ask(self,
                base_currency: str,
                quote_currency: str = Defaults.QUOTE_CURRENCY):
        raise NotImplementedError

    def bid(self, currency: str):
        return self.bid_ask(currency).get('bid')

    def ask(self, currency: str):
        return self.bid_ask(currency).get('ask')


class WebsocketTickerMixin(LiveUpdateMixin):
    _websocket_class = None

    def __init__(self, *args, **kwargs):
        self._websocket = self._websocket_class()
        self._bid_ask = {}
        super(WebsocketTickerMixin, self).__init__(*args, **kwargs)

    def start_live_updates(self, base_currency: Union[str, List[str]], quote_currency: str):
        self._websocket.start()
        if isinstance(base_currency, str):
            base_currency = [base_currency]
        for currency in base_currency:
            self._bid_ask[currency] = {'bid': None, 'ask': None, 'time': None}
            self._websocket.subscribe('ticker', currency, quote_currency)

    def stop_live_updates(self):
        self._websocket.stop()

    def _update(self):
        message = None
        while not self._websocket.queue.empty():
            message = self._websocket.queue.get()
        if message:
            pair, bid_ask = message
            base, quote = self.formatter.unpair(pair)
            log.debug('{exchange} {currency} {bid_ask}', event_name='websocket_mixin.update',
                      event_data={'exchange': self.name, 'currency': base, 'bid_ask': format_bid_ask(bid_ask)})
            self._bid_ask[base] = bid_ask

    def bid_ask(self,
                base_currency: str,
                quote_currency: str = Defaults.QUOTE_CURRENCY):
        self._update()
        return self._bid_ask[base_currency]


class PeriodicRefreshMixin(LiveUpdateMixin):

    def __init__(self, refresh_interval: int, *args, **kwargs):
        self._interval = refresh_interval
        self._running = Event()
        self._lock = RLock()
        self._refresh_threads = {}
        self._bid_ask = {'bid': None, 'ask': None, 'time': None}
        super(PeriodicRefreshMixin, self).__init__(*args, **kwargs)

    def start_live_updates(self, base_currency: Union[str, List[str]], quote_currency: str = Defaults.QUOTE_CURRENCY):
        if isinstance(base_currency, str):
            base_currency = [base_currency]
        for currency in base_currency:
            if not thread_running(self._refresh_threads.get(currency)):
                self._base = base_currency
                self._quote = quote_currency
                self._running.set()
                self._refresh_threads[currency] = Thread(target=partial(self._refresh, currency), daemon=True,
                                                         name='{}{}RefreshThread'.format(self.name.title(), currency))
                self._refresh_threads[currency].start()

    def stop_live_updates(self):
        self._running.clear()
        for currency, thread in self._refresh_threads.items():
            if thread_running(thread):
                thread.join()

    def _refresh(self, currency):
        while self._running.is_set():
            try:
                ticker = self.ticker(currency, quote_currency=self._quote)
            except RequestException as e:
                log.warning('Exception while connecting to {exchange}: {exception}',
                            event_name='refresh_mixin.request_error',
                            event_data={'exchange': self.name, 'exception': e})
            else:
                bid_ask = {
                    'bid': ticker.get('bid'),
                    'ask': ticker.get('ask'),
                    'time': ticker.get('time', time.time())
                }
                with self._lock:
                    self._bid_ask[currency] = bid_ask
                    log.debug('{exchange} {currency} {bid_ask}', event_name='refresh_mixin.update',
                              event_data={'exchange': self.name, 'currency': currency,
                                          'bid_ask': format_bid_ask(bid_ask)})
            time.sleep(self._interval)

    def bid_ask(self, currency: Optional[str] = None):
        with self._lock:
            # TODO: do we actually need to acquire the lock here?
            # should we be creating a copy of the dict instead of passing a reference?
            if currency:
                return self._bid_ask.get(currency, {'bid': None, 'ask': None, 'time': None})
            return self._bid_ask


class SeparateTradingAccountMixin(object):

    def bank_balance(self) -> Dict[str, float]:
        raise NotImplementedError

    def _transfer_between_accounts(self, to_trading: bool, currency: str, amount: float) -> bool:
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


class ProxyCurrencyWrapper(object):
    float_precision = 4

    def __init__(self,
                 api,
                 proxy_currency: str,
                 quote_currency: str,
                 acceptable_bid: float = None,
                 acceptable_ask: float = None):
        """
        :param proxy_currency: the currency considered to be the "quote" currency by the client of the API
        :param quote_currency: the actual quote currency that will be used on the exchange
        """
        self._api = api
        self.quote_currency = quote_currency
        self.proxy_currency = proxy_currency
        self.acceptable_bid = acceptable_bid
        self.acceptable_ask = acceptable_ask

    def __getattr__(self, name: str):
        attr = getattr(self._api, name)
        if not callable(attr):
            return attr
        return self._proxy_wrapper(attr)

    def _proxy_wrapper(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            quote = kwargs.get('quote_currency')
            if quote and quote == self.proxy_currency:
                kwargs['quote_currency'] = self.quote_currency
            result = func(*args, **kwargs)
            # TODO: reverse proxy?
            return result
        return wrapper

    def balance(self, show_quote: bool = False):
        balances = self._api.balance()
        if not show_quote:
            quote_bal = balances.pop(self.quote_currency, 0.)
            proxy_bal = balances.pop(self.proxy_currency, 0.)
            balances[self.proxy_currency] = quote_bal + proxy_bal
        return balances

    def withdraw(self, currency: str, address: str, amount: float, **kwargs) -> str:
        if currency == self.proxy_currency:
            balance = self.balance(show_quote=True)
            proxy_bal = balance.get(self.proxy_currency, 0.)
            if proxy_bal < amount:
                transfer_amt = amount - proxy_bal
                self.quote_to_proxy(transfer_amt)
        return self._api.withdraw(currency, address, amount, **kwargs)

    def proxy_to_quote(self, amount: float = None):
        proxy_bid = self._api.ticker(self.proxy_currency, quote_currency=self.quote_currency)['bid']

        if self.acceptable_bid and proxy_bid < self.acceptable_bid:
            log_msg = ('{exchange} {proxy}/{quote} bid is {actual_bid} which '
                       'is lower than the acceptable bid of {acceptable_bid}')
            log.error(log_msg, event_name='proxy_order.unacceptable_price',
                      event_data={'exchange': self._api.name, 'proxy': self.proxy_currency,
                                  'quote': self.quote_currency, 'actual_bid': proxy_bid,
                                  'acceptable_bid': self.acceptable_bid})
            raise ExchangeError('Unable to exchange proxy currency for quote currency')

        if amount is None:
            amount = self.balance(show_quote=True).get(self.proxy_currency, 0.)
        price = '{:.{prec}f}'.format(proxy_bid * (1 - Defaults.ORDER_PRECISION), prec=self.float_precision)

        if amount > 0:
            order_id = self._api.limit_order(self.proxy_currency, 'sell', price, amount,
                                             quote_currency=self.quote_currency)
            return self._api.wait_for_fill(order_id)

    def quote_to_proxy(self, amount: float = None):
        proxy_ask = self._api.ticker(self.proxy_currency, quote_currency=self.quote_currency)['ask']

        if self.acceptable_ask and proxy_ask > self.acceptable_ask:
            log_msg = ('{exchange} {proxy}/{quote} ask is {actual_ask} which '
                       'is higher than the acceptable ask of {acceptable_ask}')
            log.error(log_msg, event_name='proxy_order.unacceptable_price',
                      event_data={'exchange': self._api.name, 'proxy': self.proxy_currency,
                                  'quote': self.quote_currency, 'actual_ask': proxy_ask,
                                  'acceptable_ask': self.acceptable_ask})
            raise ExchangeError('Unable to exchange quote currency for proxy currency')

        price = '{:.{prec}f}'.format(proxy_ask * (1 + Defaults.ORDER_PRECISION), prec=self.float_precision)
        if amount is None:
            amount = self.balance(show_quote=True).get(self.quote_currency, 0.) / price

        if amount > 0:
            order_id = self._api.limit_order(self.proxy_currency, 'buy', price, amount,
                                             quote_currency=self.quote_currency)
            return self._api.wait_for_fill(order_id)
