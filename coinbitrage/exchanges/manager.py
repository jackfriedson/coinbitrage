import time
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

    def __init__(self, exchanges: List[str], base_currency: str, quote_currency: str, loop = None):
        self.base_currency = base_currency
        self.quote_currency = quote_currency
        self._loop = loop or asyncio.get_event_loop()
        self._buy_active = self._sell_active = set()
        self._balances = None
        self._total_balances = {}
        self._clients = {
            exchg.name: exchg
            for exchg in (get_exchange(name) for name in exchanges)
            if exchg.supports_pair(base_currency, quote_currency)
        }
        self._update_trading_balances()

    def get(self, exchange_name: str):
        return self._clients.get(exchange_name)

    @property
    def balances(self):
        return self._balances

    @property
    def total_balances(self):
        return self._total_balances

    def manage_balances(self):
        self._pre_distribute_step()
        self._update_trading_balances()
        self._redistribute(self.base_currency)
        self._redistribute(self.quote_currency)
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

    def _redistribute(self, currency: str):
        total_balance = self._total_balances.get(currency, 0.)
        order_size = CURRENCIES[currency]['order_size']
        average_balance = (total_balance - order_size) / len(self._clients)
        min_transfer = CURRENCIES[currency]['min_transfer_size']

        debts = {}
        credits = {}

        for exchg, balances in self._balances.items():
            balance = balances.get(currency, 0.)
            if balance < order_size:
                debts[exchg] = average_balance - balance
            elif balance > average_balance + min_transfer:
                credits[exchg] = balance - average_balance

        log.debug('{} debts: {}'.format(currency, debts))
        log.debug('{} credits: {}'.format(currency, credits))

        try:
            while debts and credits:
                to_exchange, debt = max(debts.items(), key=lambda x: x[1])
                from_exchange, credit = max(credits.items(), key=lambda x: x[1])
                to_exchange_client = self.get(to_exchange)
                from_exchange_client = self.get(from_exchange)

                if debt < credit:
                    transfer_amt = max(debt, min_transfer)
                    to_exchange_client.get_funds_from(from_exchange_client, currency, transfer_amt)
                    debts.pop(to_exchange)
                    credits[from_exchange] = credit - transfer_amt
                    if credits[from_exchange] < min_transfer:
                        credits.pop(from_exchange)
                else:
                    assert credit >= min_transfer
                    to_exchange_client.get_funds_from(from_exchange_client, currency, credit)
                    credits.pop(from_exchange)
                    debts[to_exchange] = debt - credit
        except Exception as e:
            log.warning('Could not successfully redistribute funds', event_name='redistribute_funds.failure',
                        event_data={'exception': e})
            raise

    def _update_trading_balances(self):
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
        self._update_trading_balances()
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
