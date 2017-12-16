import asyncio
import logging
import time
from contextlib import contextmanager
from functools import partial
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd
from requests.exceptions import RequestException, Timeout

from coinbitrage import bitlogging, settings
from coinbitrage.exchanges.errors import ServerError
from coinbitrage.exchanges.manager import ExchangeManager
from coinbitrage.exchanges.mixins import SeparateTradingAccountMixin
from coinbitrage.settings import CURRENCIES, MAX_TRANSFER_FEE
from coinbitrage.utils import RunEvery, retry_on_exception


COLOR_THRESH = 0.005
REBALANCE_FUNDS_EVERY = 60 * 5  # Rebalance funds every 5 minutes
PRINT_TABLE_EVERY = 60 * 1  # Print table every minute


log = bitlogging.getLogger(__name__)


class ArbitrageEngine(object):

    def __init__(self,
                 exchanges: List[str],
                 base_currency: str,
                 quote_currency: str,
                 min_profit: float = 0.):
        self.base_currency = base_currency
        self.quote_currency = quote_currency
        self._loop = asyncio.get_event_loop()
        self._exchanges = ExchangeManager(exchanges, base_currency, quote_currency, loop=self._loop)
        self._min_profit_threshold = min_profit

    def run(self):
        """Runs the program."""
        manage_balances = RunEvery(self._exchanges.manage_balances, delay=REBALANCE_FUNDS_EVERY)
        print_table = RunEvery(self._print_arbitrage_table, delay=PRINT_TABLE_EVERY)

        with self._exchanges.live_updates():
            try:
                while True:
                    manage_balances()
                    self._attempt_arbitrage()
                    print_table()
            except KeyboardInterrupt:
                pass
            except Exception as e:
                log.exception(e, event_name='error.general')
            finally:
                self._loop.close()

    def _print_arbitrage_table(self):
        table = self.arbitrage_table()
        table = table.applymap(lambda x: '{:.2f}%'.format(x*100) if x else None)
        print()
        print(table)
        print()

    def _attempt_arbitrage(self):
        """Checks the arbitrage table to determine if there is an opportunity to profit,
        and if so executes the corresponding trades.
        """
        arbitrage_opportunity = self._maximum_profit()

        if arbitrage_opportunity:
            buy_exchange, sell_exchange, expected_profit = arbitrage_opportunity

            buy_fee = buy_exchange.fee(self.base_currency)
            sell_fee = sell_exchange.fee(self.base_currency)
            expected_profit -= (buy_fee + sell_fee + (2*MAX_TRANSFER_FEE))

            if expected_profit > self._min_profit_threshold:
                self._place_orders(buy_exchange, sell_exchange, expected_profit)

    def _maximum_profit(self):
        """Determines the maximum profit attainable given the current prices.

        :returns: a tuple representing the exchanges to buy and sell at, and the expected profit
        """
        # Determine the best exchanges to buy and sell at
        best_buy_exchange = min(self._exchanges.valid_buys(), key=lambda x: x.ask(), default=None)
        best_sell_exchange = max(self._exchanges.valid_sells(), key=lambda x: x.bid(), default=None)

        if not (best_buy_exchange and best_sell_exchange):
            return None

        expected_profit = self._arbitrage_profit_loss(best_buy_exchange, best_sell_exchange)

        if not expected_profit:
            return None

        return best_buy_exchange, best_sell_exchange, expected_profit

    def _arbitrage_profit_loss(self, buy_exchange, sell_exchange) -> float:
        """Calculates the profit/loss of buying at one exchange and selling at another.

        :param buy_exchange: the exchange to buy from
        :param sell_exchange: the exchange to sell to
        """
        if buy_exchange.name == sell_exchange.name:
            return None

        sell_exchange_price = sell_exchange.bid()
        buy_exchange_price = buy_exchange.ask()

        if not (sell_exchange_price and buy_exchange_price):
            return None

        return (sell_exchange_price / buy_exchange_price) - 1.

    def _place_orders(self, buy_exchange, sell_exchange, expected_profit: float):
        """Places buy and sell orders at the corresponding exchanges.

        :param buy_exchange: The name of the exchange to buy from
        :param sell_exchange: The name of the excahnge to sell at
        :param expected_profit: The percent profit that can be expected
        """
        buy_price = buy_exchange.ask() * (1 + settings.ORDER_PRECISION)
        sell_price = sell_exchange.bid() * (1 - settings.ORDER_PRECISION)

        # Compute the order size
        multiplier = 2**int(expected_profit * 100)
        assert multiplier > 0
        target_volume = CURRENCIES[self.base_currency]['order_size'] * multiplier
        buy_balance = self._exchange_balances[buy_exchange][self.quote_currency] / buy_price
        sell_balance = self._exchange_balances[sell_exchange][self.base_currency]
        order_volume = min(target_volume, buy_balance, sell_balance)

        if order_volume < CURRENCIES[self.base_currency]['order_size']:
            log.warning('Attempted arbitrage with insufficient funds; ' + \
                        '{buy_exchange} buy: {buy_balance}; {sell_exchange} sell: {sell_balance}',
                        event_data={'buy_exchange': buy_exchange.name, 'buy_balance': buy_balance,
                                    'sell_exchange': sell_exchange.name, 'sell_balance': sell_balance,
                                    'target_volume': target_volume},
                        event_name='arbitrage.insufficient_funds')
            self._exchanges.update_active()
            return

        log_msg = 'Arbitrage opportunity: ' + \
                  '{buy_exchange} buy {volume} {base_currency} @ {buy_price}; ' + \
                  '{sell_exchange} sell {volume} {quote_currency} @ {sell_price}; ' + \
                  'profit: {expected_profit:.2f}%'
        event_data = {'buy_exchange': buy_exchange.name, 'sell_exchange': sell_exchange.name, 'volume': order_volume,
                      'base_currency': self.base_currency, 'quote_currency': self.quote_currency,
                      'buy_price': buy_price, 'sell_price': sell_price, 'expected_profit': expected_profit*100}
        log.info(log_msg, event_name='arbitrage.attempt', event_data=event_data)

        partial_buy_order = partial(buy_exchange.limit_order, self.base_currency, 'buy',
                                    buy_price, order_volume, quote_currency=self.quote_currency, fill_or_kill=True)
        partial_sell_order = partial(sell_exchange.limit_order, self.base_currency, 'sell',
                                     sell_price, order_volume, quote_currency=self.quote_currency, fill_or_kill=True)

        # Place buy and sell orders asynchronously
        buy_resp, sell_resp = self._place_orders_async(partial_buy_order, partial_sell_order)

        if buy_resp and sell_resp:
            log.info('Both orders placed successfully', event_name='arbitrage.place_order.success',
                     event_data={'buy_order_id': buy_resp, 'sell_order_id': sell_resp})
            self._exchanges.update_active()
        elif (buy_resp and not sell_resp) or (sell_resp and not buy_resp):
            if buy_resp:
                success_side, fail_side, client, resp = 'buy', 'sell', buy_exchange, buy_resp
            else:
                success_side, fail_side, client, resp = 'sell', 'buy', sell_exchange, sell_resp

            log.warning('{} order failed, attempting to cancel {} order'.format(fail_side.title(), success_side),
                        event_name='arbitrage.place_order.partial_failure')
            cancel_success = client.cancel_order(resp)
            if cancel_success:
                log.info('Order cancelled successfully'.format(success_side),
                         event_name='cancel_order.success', event_data={'order_id': resp})
            else:
                log.warning('Order could not be cancelled'.format(success_side),
                            event_name='cancel_order.failure', event_data={'order_id': resp})
                raise Exception
        else:
            log.warning('Both orders failed', event_name='arbitrage.place_order.total_failure')
            raise Exception

    def _place_orders_async(self, buy_partial: Callable[[], Optional[str]],
                                  sell_partial: Callable[[], Optional[str]]) -> Tuple[Optional[str], Optional[str]]:
        async def place_order_async(partial_fn: Callable[[], Optional[str]]):
            try:
                return partial_fn()
            except RequestException as e:
                log.error(e, event_name='place_order.error')
                return False

        futures = [place_order_async(buy_partial), place_order_async(sell_partial)]
        return tuple(self._loop.run_until_complete(asyncio.gather(*futures)))

    def arbitrage_table(self) -> pd.DataFrame:
        """Creates a table where rows represent to the exchange to buy from, and columns
        represent the exchange to sell to. The entry in each cell represents the percent profit/loss
        that would result from buying at the "buy" exchange and selling at the "sell" exchange.

        :returns: a dataframe representing the current arbitrage table
        """
        buy_exchanges = {x.name: x for x in self._exchanges.valid_buys()}
        sell_exchanges = {x.name: x for x in self._exchanges.valid_sells()}

        result = pd.DataFrame(index=buy_exchanges.keys(), columns=sell_exchanges.keys())

        for buy_name, buy_exchg in buy_exchanges.items():
            for sell_name, sell_exchg in sell_exchanges.items():
                result.loc[buy_name, sell_name] = self._arbitrage_profit_loss(buy_exchg, sell_exchg)

        return result
