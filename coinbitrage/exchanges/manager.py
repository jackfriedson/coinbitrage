import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from functools import partial
from typing import Dict, List, Union

import asyncio
from requests.exceptions import RequestException, Timeout

from coinbitrage import bitlogging
from coinbitrage.exchanges import get_exchange
from coinbitrage.exchanges.errors import ClientError, ServerError
from coinbitrage.exchanges.mixins import ProxyCurrencyWrapper, SeparateTradingAccountMixin
from coinbitrage.settings import CURRENCIES, Defaults


log = bitlogging.getLogger(__name__)


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
        self.tx_credits = initial_tx_credit  # In quote currency
        self.all_currencies = self.base_currencies + [quote_currency]
        self._loop = loop or asyncio.get_event_loop()
        self._balances = {}
        self._clients = {}
        self._order_history = defaultdict(list)
        self._init_clients([get_exchange(name) for name in exchanges])
        self.update_trading_balances()

    # TODO: implement withdraw-all function to transfer funds (of a particular currency) from all exchanges
    # to a single address

    def _init_clients(self, clients: list):
        with ThreadPoolExecutor(max_workers=len(clients)) as executor:
            futures = [self._loop.run_in_executor(executor, exchg.init) for exchg in clients]
            self._loop.run_until_complete(asyncio.gather(*futures))

        self._clients = {
            exchg.name: exchg for exchg in clients
            if any(exchg.supports_pair(base, self.quote_currency) for base in self.base_currencies)
        }

    @contextmanager
    def live_updates(self):
        """A context manager for opening and closing resources associated with
        exchanges."""
        try:
            for exchange in self.exchanges:
                exchange.start_live_updates(self.base_currencies, self.quote_currency)
            yield
        finally:
            for exchange in self.exchanges:
                exchange.stop_live_updates()

    def get(self, exchange_name: str):
        return self._clients.get(exchange_name)

    def balance(self, exchange: str, currency: str):
        return self._balances[exchange][currency]

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

    @property
    def exchanges(self):
        return list(filter(lambda x: not x.breaker_tripped, self._clients.values()))

    def manage_exchanges(self):
        log.info('Total balances: {totals}', event_name='update.total_balances',
                 event_data={'totals': self.totals()})
        self._pre_distribute_step()
        self.update_trading_balances()
        for currency in self.base_currencies:
            self._redistribute_base(currency)
        # self._redistribute_quote()
        self.update_trading_balances()
        self._pre_trading_step()


    def buy_exchanges(self, base_currency: str):
        def buy_exchange_filter(exchange):
            return all([
                # Supports this trading pair
                exchange.supports_pair(base_currency, self.quote_currency),
                # Balance is above minimum
                self._balances[exchange.name].get(self.quote_currency, 0.) >= CURRENCIES[self.quote_currency]['min_order_size'],
                # Has been updated recently
                exchange.updated_recently(base_currency, self.quote_currency, Defaults.STALE_DATA_TIMEOUT)
            ])

        return filter(buy_exchange_filter, self.exchanges)

    def sell_exchanges(self, base_currency: str):
        def sell_exchange_filter(exchange):
            return all([
                # Supports this trading pair
                exchange.supports_pair(base_currency, self.quote_currency),
                # Balance is above minimum
                self._balances[exchange.name].get(base_currency, 0.) >= CURRENCIES[base_currency]['min_order_size'],
                # Has been updated recently
                exchange.updated_recently(base_currency, self.quote_currency, Defaults.STALE_DATA_TIMEOUT)
            ])

        return filter(sell_exchange_filter, self.exchanges)

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

    def _pre_distribute_step(self):
        self._check_open_circuits()
        self._transfer_to_trading_accounts()

    def _pre_trading_step(self):
        self._exchange_proxy_currencies()

    def _check_open_circuits(self):
        for exchg in self._clients.values():
            if exchg.breaker_tripped:
                try:
                    exchg.breaker_tripped['retry']()
                except exchg.breaker_tripped['exc_types']:
                    pass
                else:
                    exchg.breaker_tripped = None

    def _transfer_to_trading_accounts(self):
        filtered_exchanges = filter(lambda x: isinstance(x.api, SeparateTradingAccountMixin), self.exchanges)

        def bank_to_trading(exchange):
            # TODO: see if we can refactor circuit breaker as a decorator or context manager
            try:
                bank_balances = exchange.bank_balance()
            except RequestException:
                exchange.trip_circuit_breaker(RequestException, partial(exchange.bank_balance))
            else:
                for currency in self.all_currencies:
                    bank_balance = bank_balances.get(currency, 0.)
                    if bank_balance > 0:
                        try:
                            exchange.bank_to_trading(currency, bank_balance)
                        except RequestException:
                            pass

        futures = [
            self._loop.run_in_executor(None, bank_to_trading, exchg)
            for exchg in filtered_exchanges
        ]
        self._loop.run_until_complete(asyncio.gather(*futures))

    def _exchange_proxy_currencies(self):
        filtered_exchanges = filter(lambda x: isinstance(x.api, ProxyCurrencyWrapper), self.exchanges)
        futures = [self._loop.run_in_executor(None, exchg.proxy_to_quote) for exchg in filtered_exchanges]
        self._loop.run_until_complete(asyncio.gather(*futures))

    def _redistribute_base(self, currency: str):
        # TODO: revisit this strategy and determine if it makes sense

        total_bal = self.totals().get(currency)
        if not total_bal:
            return
        target_bal = total_bal / len(self._clients)

        initialized_exchanges = filter(lambda x: x.order_book_initialized(currency, self.quote_currency), self.exchanges)
        best_price = max(initialized_exchanges, key=lambda x: x.bid(currency))
        lo_bal = self._balances[best_price.name].get(currency, 0.)
        # TODO: Use best history once we have enough data

        hi_bal_name, balances = max(self._balances.items(), key=lambda x: x[1].get(currency, 0.))
        hi_bal = balances[currency]
        highest_balance = self.get(hi_bal_name)

        if best_price.name == highest_balance.name or lo_bal >= hi_bal:
            return

        transfer_amt = max(hi_bal - target_bal, target_bal - lo_bal)

        if transfer_amt <= CURRENCIES[currency]['min_order_size']:
            return

        tx_fee = highest_balance.tx_fee(currency) * highest_balance.bid(currency)
        if tx_fee > self.tx_credits:
            return

        try:
            if best_price.get_funds_from(highest_balance, currency, transfer_amt):
                self.tx_credits -= tx_fee
        except (ClientError, ServerError, RequestException, Timeout) as e:
            log.info('Encountered error while trying to rebalance funds',
                     event_name='rebalance_base.failure',
                     event_data={'error': e})
            return

    # TODO: implement redistribution of quote currency only when there is a
    # severe imbalance (and it is possible to rebalance)
    def _redistribute_quote(self):
        sufficient_balances = [
            x for x in self.balances().items()
            if x[1][self.quote_currency] > CURRENCIES[self.quote_currency]['min_order_size']
        ]

        if len(sufficient_balances) != 1:
            return

        transfer_from_exchg = self.get(sufficient_balances[0])

        tx_fee = transfer_from_exchg.tx_fee(self.quote_currency)

        min_transfer_amount = tx_fee * (1 / Defaults.MAX_QUOTE_TRANSFER_PCT)
        if excess_bal < min_transfer_amount:
            return

        best_price_counts = defaultdict(int)
        for base in self.base_currencies:
            best_exchg = min(self.exchanges, key=lambda x: x.ask(base))
            best_price_counts[best_exchg.name] += 1

        best_exchg_name, _ = max(best_price_counts.items(), key=lambda x: x[1])
        transfer_to_exchg = self.get(best_exchg_name)

        # if not all([x.ask() for x in self.exchanges]):
        #     return

        # best_price = min(self.exchanges, key=lambda x: x.ask())
        # # TODO: Use best history once we have enough data

        # hi_bal_name, hi_bal = max(self._balances.items(), key=lambda x: x[1][self.quote_currency])
        # highest_balance = self.get(hi_bal_name)

        # if best_price.name == highest_balance.name:
        #     return

        # tx_fee = highest_balance.tx_fee(self.quote_currency)
        # if tx_fee > self.tx_credits:
        #     return

        # if best_price.get_funds_from(highest_balance, self.quote_currency, hi_bal[self.quote_currency]):
        #     self.tx_credits -= tx_fee

    def update_trading_balances(self):
        def get_balance(exchange):
            try:
                return exchange.name, exchange.balance()
            except RequestException as e:
                exchange.trip_circuit_breaker(RequestException, partial(exchange.balance))
                return None

        with ThreadPoolExecutor(max_workers=len(self._clients)) as executor:
            futures = [
                self._loop.run_in_executor(executor, get_balance, exchg)
                for exchg in self.exchanges
            ]
            results = self._loop.run_until_complete(asyncio.gather(*futures))

        self._balances = {
            name: {
                cur: bal for cur, bal in balances.items()
            } for name, balances in filter(None, results)
        }
