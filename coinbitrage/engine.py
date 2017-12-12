import asyncio
import logging
import time
from contextlib import contextmanager
from functools import partial
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd
from requests.exceptions import RequestException, Timeout

from coinbitrage import bitlogging, settings
from coinbitrage.exchanges import get_exchange
from coinbitrage.exchanges.errors import ServerError
from coinbitrage.exchanges.mixins import SeparateTradingAccountMixin
from coinbitrage.exchanges.utils import retry_on_exception
from coinbitrage.settings import CURRENCIES, ESTIMATED_TRANSFER_FEE


BALANCE_MARGIN = 0.2
COLOR_THRESH = 0.005
REBALANCE_FUNDS_EVERY = 60 * 5  # Rebalance funds every 5 minutes
PRINT_TABLE_EVERY = 60 * 1  # Print table every minute
MAX_REFRESH_DELAY = 10  # Filter exchanges not updated within the last 10 seconds


log = bitlogging.getLogger(__name__)


class ArbitrageEngine(object):

    def __init__(self,
                 exchanges: List[str],
                 base_currency: str,
                 quote_currency: str,
                 min_profit: float = 0.,
                 order_precision: float = 0.002):
        self.buy_exchanges = self.sell_exchanges = []
        self.base_currency = base_currency
        self.quote_currency = quote_currency
        self.total_balances = {base_currency: None, quote_currency: None}
        self._min_profit_threshold = min_profit
        self._acceptable_limit_margin = order_precision

        self._exchanges = {name: get_exchange(name) for name in exchanges}
        self._exchange_balances = None
        self._last_prices = {exchg: {'bid': None, 'ask': None, 'time': None} for exchg in exchanges}

        #TODO
        # self._get_latest_tx_fees()

    def run(self):
        """Runs the program."""
        with self._exchange_manager():
            loop = asyncio.get_event_loop()
            loop.create_task(self._manage_balances(loop))
            loop.create_task(self._arbitrage(loop))
            loop.call_later(PRINT_TABLE_EVERY, self._print_arbitrage_table, loop)
            try:
                loop.run_forever()
            except KeyboardInterrupt:
                pass
            except Exception as e:
                log.exception(e, event_name='error.general')
            finally:
                loop.close()

    async def _arbitrage(self, loop):
        try:
            self._update_prices()
            await self._attempt_arbitrage()
            loop.create_task(self._arbitrage(loop))
        except Exception as e:
            log.exception(e, event_name='error.arbitrage')
            loop.stop()

    async def _manage_balances(self, loop):
        log.debug('Managing balances...', event_name='balance_manager.start')
        try:
            self._transfer_to_trading_accounts()
            await self._update_exchange_balances()
            self._redistribute_funds()
            await self._update_active_exchanges()
            await asyncio.sleep(REBALANCE_FUNDS_EVERY)
            loop.create_task(self._manage_balances(loop))
        except Exception as e:
            log.exception(e, event_name='error.manage_balances')
            loop.stop()

    @staticmethod
    @retry_on_exception(Timeout, ServerError)
    async def _get_balance_async(name: str, exchange):
        return name, exchange.balance()

    async def _update_exchange_balances(self):
        futures = [self._get_balance_async(name, exchg) for name, exchg in self._exchanges.items()]
        results = await asyncio.gather(*futures)
        self._exchange_balances = {
            name: {
                cur: bal for cur, bal in balances.items()
                if cur in [self.base_currency, self.quote_currency]
            } for name, balances in results
        }
        new_totals = {
            cur: sum([bal[cur] for bal in self._exchange_balances.values()])
            for cur in [self.base_currency, self.quote_currency]
        }
        if new_totals != self.total_balances:
            log.info('Updated balances: {total_balances}', event_name='balances.update',
                     event_data={'total_balances': new_totals, 'full_balances': self._exchange_balances})
        self.total_balances = new_totals

    def _print_arbitrage_table(self, loop):
        try:
            table = self.arbitrage_table()
            table = table.applymap(lambda x: '{:.2f}%'.format(x*100) if x else None)
            print('\n ARBITRAGE TABLE')
            print('-----------------')
            print(table)
            print()
            loop.call_later(PRINT_TABLE_EVERY, self._print_arbitrage_table, loop)
        except Exception as e:
            log.exception(e, event_name='error.print_table')
            loop.stop()

    def _transfer_to_trading_accounts(self):
        for exchange in self._exchanges.values():
            if isinstance(exchange.api, SeparateTradingAccountMixin):
                bank_balances = exchange.bank_balance()
                base_bank_bal = bank_balances[self.base_currency]
                quote_bank_bal = bank_balances[self.quote_currency]

                if base_bank_bal > 0:
                    exchange.bank_to_trading(self.base_currency, base_bank_bal)
                if quote_bank_bal > 0:
                    exchange.bank_to_trading(self.quote_currency, quote_bank_bal)

    def _redistribute_funds(self):
        def redistribute(currency: str):
            total_balance = self.total_balances[currency]
            order_size = CURRENCIES[currency]['order_size']
            average_balance = (total_balance - order_size) / len(self._exchanges)
            min_transfer = CURRENCIES[currency]['min_transfer_size']

            debts = {}
            credits = {}

            for exchg, balances in self._exchange_balances.items():
                balance = balances[currency]
                if balance < order_size:
                    debts[exchg] = average_balance - balance
                elif balance > average_balance + min_transfer:
                    credits[exchg] = balance - average_balance

            log.debug('{} debts: {}'.format(currency, debts))
            log.debug('{} credits: {}'.format(currency, credits))

            while debts and credits:
                to_exchange, debt = max(debts.items(), key=lambda x: x[1])
                from_exchange, credit = max(credits.items(), key=lambda x: x[1])
                to_exchange_client = self._exchanges[to_exchange]
                from_exchange_client = self._exchanges[from_exchange]

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

        redistribute(self.base_currency)
        redistribute(self.quote_currency)

    async def _update_active_exchanges(self):
        await self._update_exchange_balances()
        self.buy_exchanges = [
            n for n, bal in self._exchange_balances.items()
            if bal[self.quote_currency] >= CURRENCIES[self.quote_currency]['order_size']
        ]
        self.sell_exchanges = [
            n for n, bal in self._exchange_balances.items()
            if bal[self.base_currency] >= CURRENCIES[self.base_currency]['order_size']
        ]
        log.info('Buy exchanges: {buy_exchanges}; Sell exchanges: {sell_exchanges}',
                 event_data={'buy_exchanges': self.buy_exchanges, 'sell_exchanges': self.sell_exchanges},
                 event_name='active_exchanges.update',)

    def _arbitrage_profit_loss(self, buy_exchange: str, sell_exchange: str) -> float:
        """Calculates the profit/loss of buying at one exchange and selling at another.

        :param buy_exchange: the exchange to buy from
        :param sell_exchange: the exchange to sell to
        """
        if buy_exchange == sell_exchange:
            return None

        sell_exchange_price = self._last_prices[sell_exchange]['bid']
        buy_exchange_price = self._last_prices[buy_exchange]['ask']

        if not (sell_exchange_price and buy_exchange_price):
            return None

        return (sell_exchange_price / buy_exchange_price) - 1.

    @contextmanager
    def _exchange_manager(self):
        """A context manager for opening and closing resources associated with
        exchanges."""
        try:
            for exchange in self._exchanges.values():
                exchange.start_live_updates(self.base_currency, self.quote_currency)
            yield
        finally:
            for exchange in self._exchanges.values():
                exchange.stop_live_updates()

    def _update_prices(self):
        """Updates the most recent price data."""
        for name, exchange in self._exchanges.items():
            self._last_prices[name] = exchange.bid_ask(self.base_currency, self.quote_currency)

    async def _attempt_arbitrage(self):
        """Checks the arbitrage table to determine if there is an opportunity to profit,
        and if so executes the corresponding trades.
        """
        if not self._exchange_balances:
            await self._update_exchange_balances()

        arbitrage_opportunity = self._maximum_profit()

        if arbitrage_opportunity:
            buy_exchange, sell_exchange, expected_profit = arbitrage_opportunity

            if expected_profit is not None:
                buy_fee = self._exchanges[buy_exchange].fee(self.base_currency)
                sell_fee = self._exchanges[sell_exchange].fee(self.base_currency)
                expected_profit -= (buy_fee + sell_fee + ESTIMATED_TRANSFER_FEE)

                if expected_profit > self._min_profit_threshold:
                    await self._place_orders(buy_exchange, sell_exchange, expected_profit)

    def _maximum_profit(self) -> Tuple[str, str, float]:
        """Determines the maximum profit attainable given the current prices.

        :returns: a tuple representing the exchanges to buy and sell at, and the expected profit
        """
        # Filter to only exchanges that we're currrently using and that have valid, live data
        def buy_exchange_filter(val: Tuple[str, dict]):
            name, last = val
            is_active = name in self.buy_exchanges
            has_price = last['ask'] is not None
            updated_recently = last['time'] and last['time'] > time.time() - MAX_REFRESH_DELAY
            return all([is_active, has_price, updated_recently])

        def sell_exchange_filter(val: Tuple[str, dict]):
            name, last = val
            is_active = name in self.sell_exchanges
            has_price = last['bid'] is not None
            updated_recently = last['time'] and last['time'] > time.time() - MAX_REFRESH_DELAY
            return all([is_active, has_price, updated_recently])

        valid_buy_exchanges = filter(buy_exchange_filter, self._last_prices.items())
        valid_sell_exchanges = filter(sell_exchange_filter, self._last_prices.items())

        # Determine the best exchanges to buy and sell at
        best_buy_exchange = min(valid_buy_exchanges, key=lambda x: x[1]['ask'], default=(None, None))[0]
        best_sell_exchange = max(valid_sell_exchanges, key=lambda x: x[1]['bid'], default=(None, None))[0]

        if not best_buy_exchange or not best_sell_exchange:
            return None

        # Compute the expected profit of this arbitrage
        max_profit = self._arbitrage_profit_loss(best_buy_exchange, best_sell_exchange)
        return best_buy_exchange, best_sell_exchange, max_profit

    async def _place_orders(self, buy_exchange: str, sell_exchange: str, expected_profit: float):
        """Places buy and sell orders at the corresponding exchanges.

        :param buy_exchange: The name of the exchange to buy from
        :param sell_exchange: The name of the excahnge to sell at
        :param expected_profit: The percent profit that can be expected
        """
        buy_price = self._last_prices[buy_exchange]['ask'] * (1 + self._acceptable_limit_margin)
        sell_price = self._last_prices[sell_exchange]['bid'] * (1 - self._acceptable_limit_margin)

        # Compute the order size
        multiplier = int(expected_profit / .01) or 1
        target_volume = CURRENCIES[self.base_currency]['order_size'] * multiplier
        buy_balance = self._exchange_balances[buy_exchange][self.quote_currency] / buy_price
        sell_balance = self._exchange_balances[sell_exchange][self.base_currency]
        order_volume = min(target_volume, buy_balance, sell_balance)

        if order_volume < CURRENCIES[self.base_currency]['order_size']:
            log.warning('Attempted arbitrage with insufficient funds; ' + \
                        '{buy_exchange} buy: {buy_balance}; {sell_exchange} sell: {sell_balance}',
                        event_data={'buy_exchange': buy_exchange, 'buy_balance': buy_balance,
                                    'sell_exchange': sell_exchange, 'sell_balance': sell_balance,
                                    'target_volume': target_volume},
                        event_name='arbitrage.insufficient_funds')
            await self._update_active_exchanges()
            return

        log_msg = 'Arbitrage opportunity: ' + \
                  '{buy_exchange} buy {volume} {base_currency} @ {buy_price}; ' + \
                  '{sell_exchange} sell {volume} {quote_currency} @ {sell_price}; ' + \
                  'profit: {expected_profit:.2f}%'
        event_data = {'buy_exchange': buy_exchange, 'sell_exchange': sell_exchange, 'volume': order_volume,
                      'base_currency': self.base_currency, 'quote_currency': self.quote_currency,
                      'buy_price': buy_price, 'sell_price': sell_price, 'expected_profit': expected_profit*100}
        log.info(log_msg, event_name='arbitrage.attempt', event_data=event_data)

        partial_buy_order = partial(self._exchanges[buy_exchange].limit_order, self.base_currency, 'buy',
                                    buy_price, order_volume, quote_currency=self.quote_currency, fill_or_kill=True)
        partial_sell_order = partial(self._exchanges[sell_exchange].limit_order, self.base_currency, 'sell',
                                     sell_price, order_volume, quote_currency=self.quote_currency, fill_or_kill=True)

        # Place buy and sell orders asynchronously
        buy_resp, sell_resp = await self._place_orders_async(partial_buy_order, partial_sell_order)

        if buy_resp and sell_resp:
            log.info('Both orders placed successfully', event_name='arbitrage.place_order.success',
                     event_data={'buy_order_id': buy_resp, 'sell_order_id': sell_resp})
            await self._update_active_exchanges()
        elif (buy_resp and not sell_resp) or (sell_resp and not buy_resp):
            if buy_resp:
                success_side, fail_side, client, resp = 'buy', 'sell', self._exchanges[buy_exchange], buy_resp
            else:
                success_side, fail_side, client, resp = 'sell', 'buy', self._exchanges[sell_exchange], sell_resp

            log.warning('{} order failed, attempting to cancel {} order'.format(fail_side.title(), success_side),
                        event_name='arbitrage.place_order.partial_failure')
            cancel_success = client.cancel_order(resp)
            if cancel_success:
                log.info('Order cancelled successfully'.format(success_side),
                         event_name='cancel_order.success', event_data={'order_id': resp})
            else:
                log.warning('Order could not be cancelled'.format(success_side),
                            event_name='cancel_order.failure', event_data={'order_id': resp})
        else:
            log.warning('Both orders failed', event_name='arbitrage.place_order.total_failure')

    async def _place_orders_async(self, buy_partial: Callable[[], Optional[str]],
                                  sell_partial: Callable[[], Optional[str]]) -> Tuple[Optional[str], Optional[str]]:
        futures = [
            self._place_order_async(buy_partial),
            self._place_order_async(sell_partial)
        ]
        responses = await asyncio.gather(*futures)
        return tuple(responses)

    @staticmethod
    async def _place_order_async(partial_fn: Callable[[], Optional[str]]):
        try:
            return partial_fn()
        except RequestException:
            return False

    def arbitrage_table(self) -> pd.DataFrame:
        """Creates a table where rows represent to the exchange to buy from, and columns
        represent the exchange to sell to. The entry in each cell represents the percent profit/loss
        that would result from buying at the "buy" exchange and selling at the "sell" exchange.

        :returns: a dataframe representing the current arbitrage table
        """
        result = pd.DataFrame(index=self.buy_exchanges, columns=self.sell_exchanges)

        for buy_exchange in self.buy_exchanges:
            for sell_exchange in self.sell_exchanges:
                result.loc[buy_exchange, sell_exchange] = self._arbitrage_profit_loss(buy_exchange, sell_exchange)

        return result


def draw_arbitrage_table(table):
    """Draws the arbitrage table."""
    def format_as_percent(x):
        if x is None:
            return '-'
        else:
            return '{:.2f}%'.format(100*x)

    def color_fn(x):
        if x is None:
            return 'white'
        if x > COLOR_THRESH:
            return 'lightgreen'
        if x < -COLOR_THRESH:
            return 'salmon'
        return 'white'

    formatted_data = [[format_as_percent(x) for x in row] for row in table.values]
    cell_colors = [[color_fn(x) for x in row] for row in table.values]

    fig, ax = plt.subplots()
    ax.axis('off')
    ax.axis('tight')
    plt.table(cellText=formatted_data, cellColours=cell_colors, loc='center',
              rowLabels=table.index.values, colLabels=table.columns.values)
    fig.tight_layout()
    plt.show()
