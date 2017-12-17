import time
from collections import defaultdict
from contextlib import contextmanager
from typing import Dict, List, Union

import asyncio
from requests.exceptions import RequestException, Timeout

from coinbitrage import bitlogging
from coinbitrage.exchanges import get_exchange
from coinbitrage.exchanges.errors import ServerError
from coinbitrage.exchanges.mixins import ProxyCurrencyWrapper, SeparateTradingAccountMixin
from coinbitrage.settings import CURRENCIES


log = bitlogging.getLogger(__name__)


MAX_REFRESH_DELAY = 10  # Filter exchanges not updated within the last 10 seconds


class ExchangeManager(object):

    # TODO: Set a flag when deposits are pending to avoid rebalancing again; check at the beginning
    #       of each rebalance whether deposits have completed and unset the flag if so

    def __init__(self, exchanges: List[str], base_currency: str, quote_currency: str, loop = None):
        self.base_currency = base_currency
        self.quote_currency = quote_currency
        self._loop = loop or asyncio.get_event_loop()
        self._buy_active = self._sell_active = set()
        self._balances = {}
        self._total_balances = {}
        self._clients = {}
        self._order_history = defaultdict(list)
        self.tx_credits = 0.  # In quote currency

        self._init_clients([get_exchange(name) for name in exchanges])
        self.update_active_exchanges()

    def _init_clients(self, all_clients: list):
        async def init(exchg):
            exchg.init()

        futures = [init(exchg) for exchg in all_clients]
        self._loop.run_until_complete(asyncio.gather(*futures))

        self._clients = {
            exchg.name: exchg for exchg in all_clients
            if exchg.supports_pair(self.base_currency, self.quote_currency)
        }

    def get(self, exchange_name: str):
        return self._clients.get(exchange_name)

    @property
    def balances(self):
        return self._balances

    @property
    def totals(self):
        return self._total_balances

    @property
    def names(self):
        return self._clients.keys()

    def manage_balances(self):
        self._pre_distribute_step()
        self.update_trading_balances()
        self._redistribute_base()
        self._redistribute_quote()
        self.update_active_exchanges()
        self._pre_trading_step()

    def valid_buys(self):
        def buy_exchange_filter(exchange):
            bid_ask = exchange.bid_ask()
            is_active = exchange.name in self._buy_active
            has_price = bid_ask['ask'] is not None
            updated_recently = bid_ask['time'] and bid_ask['time'] > time.time() - MAX_REFRESH_DELAY
            return all([is_active, has_price, updated_recently])

        return filter(buy_exchange_filter, self._clients.values())

    def valid_sells(self):
        def sell_exchange_filter(exchange):
            bid_ask = exchange.bid_ask()
            is_active = exchange.name in self._sell_active
            has_price = bid_ask['bid'] is not None
            updated_recently = bid_ask['time'] and bid_ask['time'] > time.time() - MAX_REFRESH_DELAY
            return all([is_active, has_price, updated_recently])

        return filter(sell_exchange_filter, self._clients.values())

    def add_order(self, side: str, exchange_name: str):
        self._order_history[side].append({'exchange': exchange_name, 'time': time.time()})

    def best_history(self, side: str) -> List[str]:
        hist = self._order_history[side]
        counts = defaultdict(int)
        for order in hist:
            # TODO: use EMA, taking time into consideration
            counts[order['exchange']] += 1
        sorted_hist = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return [x[0] for x in sorted_hist]

    @contextmanager
    def live_updates(self):
        """A context manager for opening and closing resources associated with
        exchanges."""
        try:
            for exchange in self._clients.values():
                exchange.start_live_updates(self.base_currency, self.quote_currency)
            yield
        finally:
            for exchange in self._clients.values():
                exchange.stop_live_updates()

    def _pre_distribute_step(self):
        self._transfer_to_trading_accounts()

    def _pre_trading_step(self):
        self._exchange_proxy_currencies()

    def _transfer_to_trading_accounts(self):
        filtered_exchanges = filter(lambda x: isinstance(x.api, SeparateTradingAccountMixin),
                                    self._clients.values())

        async def bank_to_trading(exchange):
            for currency in [self.base_currency, self.quote_currency]:
                bank_balance = exchange.bank_balance().get(currency, 0.)
                if bank_balance > 0:
                    exchange.bank_to_trading(currency, bank_balance)

        futures = [bank_to_trading(exchg) for exchg in filtered_exchanges]
        self._loop.run_until_complete(asyncio.gather(*futures))

    def _exchange_proxy_currencies(self):
        filtered_exchanges = filter(lambda x: isinstance(x.api, ProxyCurrencyWrapper),
                                    self._clients.values())

        async def proxy_to_quote(exchange):
            exchange.proxy_to_quote()

        futures = [proxy_to_quote(exchg) for exchg in filtered_exchanges]
        self._loop.run_until_complete(asyncio.gather(*futures))

    def _redistribute_base(self):
        if not self._total_balances.get(self.base_currency, 0.):
            return

        if not all([x.bid() for x in self._clients.values()]):
            return

        best_price = max(self._clients.values(), key=lambda x: x.bid())
        # TODO: Use best history once we have enough data

        hi_bal_name, hi_bal = max(self._balances.items(), key=lambda x: x[1][self.base_currency])
        highest_balance = self.get(hi_bal_name)

        if best_price.name == highest_balance.name:
            return

        tx_fee = highest_balance.tx_fee(self.base_currency) * highest_balance.bid()
        if tx_fee > self.tx_credits:
            return

        if best_price.get_funds_from(highest_balance, self.base_currency, hi_bal[self.base_currency]):
            self.tx_credits -= tx_fee

    def _redistribute_quote(self):
        if not self._total_balances.get(self.quote_currency, 0.):
            return

        if not all([x.ask() for x in self._clients.values()]):
            return

        best_price = min(self._clients.values(), key=lambda x: x.ask())
        # TODO: Use best history once we have enough data

        hi_bal_name, hi_bal = max(self._balances.items(), key=lambda x: x[1][self.quote_currency])
        highest_balance = self.get(hi_bal_name)

        if best_price.name == highest_balance.name:
            return

        tx_fee = highest_balance.tx_fee(self.quote_currency)
        if tx_fee > self.tx_credits:
            return

        if best_price.get_funds_from(highest_balance, self.quote_currency, hi_bal[self.quote_currency]):
            self.tx_credits -= tx_fee

    def update_trading_balances(self):
        async def get_balance(exchange):
            return exchange.name, exchange.balance()

        futures = [get_balance(exchg) for exchg in self._clients.values()]
        results = self._loop.run_until_complete(asyncio.gather(*futures))

        self._balances = {
            name: {
                cur: bal for cur, bal in balances.items()
                if cur in [self.base_currency, self.quote_currency]
            } for name, balances in results
        }

        new_totals = {
            cur: sum([bal.get(cur, 0.) for bal in self._balances.values()])
            for cur in [self.base_currency, self.quote_currency]
        }

        if new_totals != self._total_balances:
            self._total_balances = new_totals
            log.info('Updated balances: {total_balances}', event_name='balances.update',
                     event_data={'total_balances': self._total_balances, 'full_balances': self._balances})

    def update_active_exchanges(self):
        self.update_trading_balances()
        self._buy_active = {
            n for n, bal in self._balances.items()
            if bal.get(self.quote_currency, 0.) >= CURRENCIES[self.quote_currency]['order_size']
        }
        self._sell_active = {
            n for n, bal in self._balances.items()
            if bal.get(self.base_currency, 0.) >= CURRENCIES[self.base_currency]['order_size']
        }
        log.info('Buy exchanges: {buy_exchanges}; Sell exchanges: {sell_exchanges}',
                 event_data={'buy_exchanges': self._buy_active, 'sell_exchanges': self._sell_active},
                 event_name='active_exchanges.update',)
