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
from coinbitrage.settings import CURRENCIES, ORDER_PRECISION


log = bitlogging.getLogger(__name__)


MAX_REFRESH_DELAY = 5  # Filter exchanges not updated within the last 5 seconds


class ExchangeManager(object):
    # TODO: Set a flag when deposits are pending to avoid rebalancing again; check at the beginning
    #       of each rebalance whether deposits have completed and unset the flag if so

    def __init__(self,
                 exchanges: List[str],
                 base_currency: Union[str, List[str]],
                 quote_currency: str,
                 loop = None,
                 initial_tx_credit: float = 0.):
        self.base_currencies = base_currency if isinstance(base_currency, list) else [base_currency]
        self.quote_currency = quote_currency
        self.all_currencies = self.base_currencies + [quote_currency]
        self._loop = loop or asyncio.get_event_loop()
        self._buy_active = self._sell_active = set()
        self._balances = {}
        self._clients = {}
        self._order_history = defaultdict(list)
        self.tx_credits = initial_tx_credit  # In quote currency

        self._init_clients([get_exchange(name) for name in exchanges])
        self.update_trading_balances()

    # TODO: implement withdraw-all function to transfer funds from all exchanges (of a single currency)
    # to a single address

    def _init_clients(self, all_clients: list):
        async def init(exchg):
            exchg.init()

        futures = [init(exchg) for exchg in all_clients]
        self._loop.run_until_complete(asyncio.gather(*futures))

        self._clients = {
            exchg.name: exchg for exchg in all_clients
            if any(exchg.supports_pair(base, self.quote_currency) for base in self.base_currencies)
        }

    def get(self, exchange_name: str):
        return self._clients.get(exchange_name)

    def balances(self, full: bool = False):
        return {
            exchg: {
                cur: bal for cur, bal in bals.items()
                if full or cur in self.all_currencies
            } for exchg, bals in self._balances.items()
        }

    def totals(self, full: bool = False):
        result = defaultdict(float)
        for exchg_balances in self.balances(full=full).values():
            for cur, bal in exchg_balances.items():
                result[cur] += bal
        return dict(result)

    @property
    def names(self):
        return self._clients.keys()

    def manage_balances(self):
        self._pre_distribute_step()
        self.update_trading_balances()
        for base in self.base_currencies:
            self._redistribute_base(base)
        self.update_trading_balances()
        self._pre_trading_step()
        log.info('Total balances: {totals}', event_name='update.total_balances',
                 event_data={'totals': self.totals()})

    def valid_buys(self, base_currency: str):
        def buy_exchange_filter(exchange):
            bid_ask = exchange.bid_ask(base_currency)
            min_balance = self._balances[exchange.name].get(self.quote_currency, 0.) >= CURRENCIES[self.quote_currency]['order_size']
            has_price = bid_ask['ask'] is not None
            updated_recently = bid_ask['time'] and bid_ask['time'] > time.time() - MAX_REFRESH_DELAY
            return all([min_balance, has_price, updated_recently])

        return filter(buy_exchange_filter, self._clients.values())

    def valid_sells(self, base_currency: str):
        def sell_exchange_filter(exchange):
            bid_ask = exchange.bid_ask(base_currency)
            min_balance = self._balances[exchange.name].get(base_currency, 0.) >= CURRENCIES[base_currency]['order_size']
            has_price = bid_ask['bid'] is not None
            updated_recently = bid_ask['time'] and bid_ask['time'] > time.time() - MAX_REFRESH_DELAY
            return all([min_balance, has_price, updated_recently])

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
                exchange.start_live_updates(self.base_currencies, self.quote_currency)
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
            for currency in self.all_currencies:
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

    def _redistribute_base(self, currency: str):
        total_bal = self.totals().get(currency)
        if not total_bal:
            return
        target_bal = total_bal / len(self._clients)

        if not all(x.bid(currency) for x in self._clients.values()):
            return

        best_price = max(self._clients.values(), key=lambda x: x.bid(currency))
        lo_bal = self._balances[best_price.name].get(currency, 0.)
        # TODO: Use best history once we have enough data

        hi_bal_name, balances = max(self._balances.items(), key=lambda x: x[1].get(currency, 0.))
        hi_bal = balances[currency]
        highest_balance = self.get(hi_bal_name)

        if best_price.name == highest_balance.name:
            return

        transfer_amt = max(hi_bal - target_bal, target_bal - lo_bal)

        tx_fee = highest_balance.tx_fee(currency) * highest_balance.bid(currency)
        if tx_fee > self.tx_credits:
            return

        if best_price.get_funds_from(highest_balance, currency, transfer_amt):
            self.tx_credits -= tx_fee

    # def _redistribute_quote(self):
    #     if not self._total_balances.get(self.quote_currency, 0.):
    #         return

    #     if not all([x.ask() for x in self._clients.values()]):
    #         return

    #     best_price = min(self._clients.values(), key=lambda x: x.ask())
    #     # TODO: Use best history once we have enough data

    #     hi_bal_name, hi_bal = max(self._balances.items(), key=lambda x: x[1][self.quote_currency])
    #     highest_balance = self.get(hi_bal_name)

    #     if best_price.name == highest_balance.name:
    #         return

    #     tx_fee = highest_balance.tx_fee(self.quote_currency)
    #     if tx_fee > self.tx_credits:
    #         return

    #     if best_price.get_funds_from(highest_balance, self.quote_currency, hi_bal[self.quote_currency]):
    #         self.tx_credits -= tx_fee

    def update_trading_balances(self):
        async def get_balance(exchange):
            return exchange.name, exchange.balance()

        futures = [get_balance(exchg) for exchg in self._clients.values()]
        results = self._loop.run_until_complete(asyncio.gather(*futures))

        self._balances = {
            name: {
                cur: bal for cur, bal in balances.items()
            } for name, balances in results
        }
