import asyncio
import copy
import logging
import time
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from functools import partial
from itertools import product
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import pandas as pd
from requests.exceptions import RequestException, Timeout

from coinbitrage import bitlogging
from coinbitrage.exchanges.errors import ServerError
from coinbitrage.exchanges.manager import ExchangeManager
from coinbitrage.exchanges.mixins import SeparateTradingAccountMixin, WebsocketOrderBookMixin
from coinbitrage.settings import CURRENCIES, Defaults
from coinbitrage.utils import RunEvery, format_floats


REBALANCE_FUNDS_EVERY = 60 * 15  # Rebalance funds every 15 minutes
PRINT_TABLE_EVERY = 60 * 1  # Print table every minute


log = bitlogging.getLogger(__name__)


OrderSpec = namedtuple('OrderSpec', ['buy_price', 'buy_limit_price', 'sell_price', 'sell_limit_price', 'order_size', 'profit'])


class ArbitrageEngine(object):

    def __init__(self,
                 exchanges: List[str],
                 base_currency: Union[str, List[str]],
                 quote_currency: str,
                 min_profit: float = 0.,
                 dry_run: bool = False,
                 **kwargs):
        self.base_currencies = base_currency if isinstance(base_currency, list) else [base_currency]
        self.quote_currency = quote_currency
        self._loop = asyncio.get_event_loop()
        self._exchanges = ExchangeManager(exchanges, base_currency, quote_currency, loop=self._loop, **kwargs)
        self._min_profit_threshold = min_profit
        self._arbitrage_table = None
        self._is_dry_run = dry_run

    def run(self, verbose: bool = False):
        """Runs the arbitrage strategy in a loop, checking at each iteration whether there is an
         opportunity to profit. Every few minutes it will perform other tasks such as rebalancing
         funds between exchanges or printing the current arbitrage table to stdout."""
        manage_exchanges = RunEvery(self._exchanges.manage_exchanges, delay=REBALANCE_FUNDS_EVERY)
        print_table = RunEvery(self._print_arbitrage_table, delay=PRINT_TABLE_EVERY)

        with self._exchanges.live_updates():
            try:
                while True:
                    manage_exchanges()
                    self._attempt_arbitrage()
                    if verbose:
                        print_table()
            except KeyboardInterrupt:
                pass
            except Exception as e:
                log.exception(e, event_name='error.general')
            finally:
                self._loop.close()

    def _print_arbitrage_table(self):
        """Print the current arbitrage table to stdout."""
        for currency in self.base_currencies:
            self.arbitrage_table(currency)
            if not self._arbitrage_table.empty:
                print()
                print(currency)
                print(self._arbitrage_table)
                print()

    def _attempt_arbitrage(self):
        """Finds the best arbitrage opportunity given the current prices and exchange fees, and
        executes the necessary trades if the expected profit exceeds the mininmum required value.
        """
        for currency in self.base_currencies:
            opportunity = self._find_best_arbitrage_opportunity(currency)
            if not opportunity:
                return

            if self._should_execute(**opportunity):
                self._execute_arbitrage(**opportunity)

    def _find_best_arbitrage_opportunity(self, base_currency: str, update_table: bool = False):
        best_opportunity = None

        # TODO: Don't find best, just check everything and execute if profitable
        for buy_exchange, sell_exchange in product(self._exchanges.buy_exchanges(base_currency), self._exchanges.sell_exchanges(base_currency)):
            if buy_exchange.name == sell_exchange.name:
                if update_table:
                    self._arbitrage_table.loc[buy_exchange.name, sell_exchange.name] = '-'
                continue

            estimated_buy_price = buy_exchange.ask(base_currency) * 1.02

            # Calculate the maximum size of the order
            buy_power = self._exchanges.balance(buy_exchange.name, self.quote_currency) / estimated_buy_price
            sell_power = self._exchanges.balance(sell_exchange.name, base_currency)
            max_order_size = min(buy_power, sell_power)

            order_spec = self._maximize_order_profit(buy_exchange, sell_exchange, base_currency, max_order_size)
            buy_price, buy_limit_price, sell_price, sell_limit_price, order_size, _ = order_spec

            # TODO: move this somewhere that makes more sense
            # if base_currency in ['ETH', 'LTC']:
            #     if buy_exchange.name == 'kraken':
            #         buy_price = float(format_floats(buy_price, 2))
            #     elif sell_exchange.name == 'kraken':
            #         sell_price = float(format_floats(sell_price, 2))
            # elif base_currency == 'XRP':
            #     if buy_exchange.name == 'kraken':
            #         buy_price = float(format_floats(buy_price, 5))
            #     elif sell_exchange.name == 'kraken':
            #         sell_price = float(format_floats(sell_price, 5))

            if sell_price < buy_price and not update_table:
                continue

            # Calculate order fees
            buy_fee = order_size * buy_price * buy_exchange.fee(base_currency, self.quote_currency)
            sell_fee = order_size * sell_price * sell_exchange.fee(base_currency, self.quote_currency)

            # Adjust order size to account for fees
            if buy_power < sell_power:
                order_size -= buy_fee / buy_price
            else:
                order_size -= sell_fee / sell_price

            if order_size < CURRENCIES[base_currency]['min_order_size'] and not update_table:
                continue

            # Calculate gross profit
            gross_percent_profit = (sell_price / buy_price) - 1
            gross_profit = gross_percent_profit * buy_price * order_size

            # Calculate transfer fees
            buy_tx_fee = buy_exchange.tx_fee(base_currency) * buy_price
            sell_tx_fee = 0.
            total_tx_fee = buy_tx_fee + sell_tx_fee

            # Calculate net profit  (assuming one transfer from buy exchange to sell exchange)
            total_fees = buy_fee + sell_fee + total_tx_fee
            net_profit = gross_profit - total_fees
            net_percent_profit = net_profit / (buy_price * order_size)

            if best_opportunity is None or net_profit > best_opportunity['net_profit']:
                # A lot of this info is for logging/debugging
                best_opportunity = {
                    'base_currency': base_currency,
                    'quote_currency': self.quote_currency,
                    'buy_exchange': buy_exchange.name,
                    'buy_price': buy_price,
                    'buy_limit_price': buy_limit_price,
                    'sell_exchange': sell_exchange.name,
                    'sell_price': sell_price,
                    'sell_limit_price': sell_limit_price,
                    'gross_percent_profit': gross_percent_profit,
                    'net_percent_profit': net_percent_profit,
                    'net_profit': net_profit,
                    'gross_profit': gross_profit,
                    'order_size': order_size,
                    'total_tx_fee': total_tx_fee,
                    'total_fees': total_fees,
                    'buy_tx_fee': buy_tx_fee,
                    'sell_tx_fee': sell_tx_fee,
                    'buy_fee': buy_fee,
                    'sell_fee': sell_fee,
                    'buy_power': buy_power,
                    'sell_power': sell_power
                }

            if update_table:
                table_val = '{:.4f} {} ({:.2f}%)'.format(net_profit, self.quote_currency, net_percent_profit*100)
                self._arbitrage_table.loc[buy_exchange.name, sell_exchange.name] = table_val

        return best_opportunity

    def _maximize_order_profit(self, buy_exchange, sell_exchange, base_currency: str, max_order_size: float) -> OrderSpec:
        buffered_order_size = max_order_size * (1 + Defaults.ORDER_BOOK_BUFFER)
        asks = iter(buy_exchange.get_asks(base_currency, self.quote_currency, buffered_order_size))
        bids = iter(sell_exchange.get_bids(base_currency, self.quote_currency, buffered_order_size))
        tx_fee = buy_exchange.tx_fee(base_currency)

        # Use brute force solution then later improve if it is a bottleneck
        ask_price, ask_size = next(asks)
        bid_price, bid_size = next(bids)

        # Take buffer off the top of the order book to make order success more likely
        buffer_remaining = max_order_size * Defaults.ORDER_BOOK_BUFFER
        while buffer_remaining > 0:
            if buffer_remaining < min(ask_size, bid_size):
                ask_size -= buffer_remaining
                bid_size -= buffer_remaining
                buffer_remaining = 0.
            elif ask_size < bid_size:
                buffer_remaining -= ask_size
                bid_size -= ask_size
                ask_price, ask_size = next(asks)
            else:
                buffer_remaining -= bid_size
                ask_size -= bid_size
                bid_price, bid_size = next(bids)

        best_order = None
        vol_remaining = max_order_size
        total_size = 0.
        ask_cost = bid_cost = 0.

        while vol_remaining > 0:
            try:
                if vol_remaining < min(ask_size, bid_size):
                    ask_cost += ask_price * vol_remaining
                    bid_cost += bid_price * vol_remaining
                    total_size += vol_remaining
                    vol_remaining = 0.
                elif ask_size < bid_size:
                    ask_cost += ask_price * ask_size
                    bid_cost += bid_price * ask_size
                    bid_size -= ask_size
                    total_size += ask_size
                    vol_remaining -= ask_size
                    ask_price, ask_size = next(asks)
                else:
                    ask_cost += ask_price * bid_size
                    bid_cost += bid_price * bid_size
                    ask_size -= bid_size
                    total_size += bid_size
                    vol_remaining -= bid_size
                    bid_price, bid_size = next(bids)

                avg_ask = ask_cost / total_size
                avg_bid = bid_cost / total_size

                gross_profit = bid_cost - ask_cost
                net_profit = gross_profit - (tx_fee * avg_ask)
                net_percent_profit = net_profit / ask_cost

                if best_order is None or net_percent_profit > best_order.profit:
                    best_order = OrderSpec(avg_ask, ask_price, avg_bid, bid_price, total_size, net_percent_profit)

            except StopIteration:
                break

        return best_order

    def _should_execute(self,
                        buy_exchange: str,
                        sell_exchange: str,
                        net_percent_profit: float,
                        **kwargs) -> bool:
        max_quote_amt = self._exchanges.totals()[self.quote_currency] * Defaults.HI_BALANCE_PERCENT

        if self._exchanges.balances()[buy_exchange][self.quote_currency] > max_quote_amt:
            return net_percent_profit > 0.

        return net_percent_profit >= self._min_profit_threshold

    def _execute_arbitrage(self,
                           base_currency: str,
                           quote_currency: str,
                           buy_exchange: str,
                           sell_exchange: str,
                           buy_limit_price: float,
                           sell_limit_price: float,
                           order_size: float,
                           total_tx_fee: float,
                           net_percent_profit: float, **kwargs):
        buy_exchange = self._exchanges.get(buy_exchange)
        sell_exchange = self._exchanges.get(sell_exchange)

        log_msg = ('Arbitrage opportunity: '
                   '{buy_exchange} buy {volume} {base_currency} @ {buy_limit_price}; '
                   '{sell_exchange} sell {volume} {base_currency} @ {sell_limit_price}; '
                   'profit: {profit:.2f}%')
        event_data = {'buy_exchange': buy_exchange.name, 'sell_exchange': sell_exchange.name,
                      'volume': order_size, 'base_currency': base_currency, 'quote_currency': quote_currency,
                      'buy_limit_price': buy_limit_price, 'sell_limit_price': sell_limit_price, 'profit': net_percent_profit*100}
        event_data.update(kwargs)
        log.info(log_msg, event_name='arbitrage.attempt', event_data=event_data)

        if not self._is_dry_run and self._place_orders(base_currency, quote_currency, buy_exchange, sell_exchange, buy_limit_price,
                                                       sell_limit_price, order_size):
            self._exchanges.add_order('buy', buy_exchange.name)
            self._exchanges.add_order('sell', sell_exchange.name)
            self._exchanges.tx_credits += total_tx_fee
            self._exchanges.update_trading_balances()

    def _place_orders(self,
                      base_currency: str,
                      quote_currency: str,
                      buy_exchange,
                      sell_exchange,
                      buy_limit_price: float,
                      sell_limit_price: float,
                      order_volume: float) -> bool:
        """Places the buy and sell orders at the corresponding exchanges.

        :param base_currency: the currency to buy/sell
        :param quote_currency: the currency that the price is denominated in
        :param buy_exchange: the exchange to buy from
        :param sell_exchange: the exchange to sell at
        :param buy_limit_price: the price of the limit buy order
        :param sell_limit_price: the price of the limit sell order
        :param order_volume: the size (in units of base currency) of both orders
        """

        def place_order(exchange, *args, **kwargs):
            try:
                return exchange.wait_for_fill(exchange.limit_order(*args, **kwargs), timeout=None)
            except RequestException as e:
                log.error(e, event_name='place_order.error')
                return None

        buy_order = partial(place_order, buy_exchange, base_currency, 'buy', buy_limit_price, order_volume, quote_currency=quote_currency)
        sell_order = partial(place_order, sell_exchange, base_currency, 'sell', sell_limit_price, order_volume, quote_currency=quote_currency)

        # place orders asynchronously to avoid missing the target price
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                self._loop.run_in_executor(executor, buy_order),
                self._loop.run_in_executor(executor, sell_order)
            ]
            buy_resp, sell_resp = tuple(self._loop.run_until_complete(asyncio.gather(*futures)))

        if buy_resp and sell_resp:
            log.info('Both orders placed successfully', event_name='arbitrage.place_order.success',
                     event_data={'buy_order': buy_resp, 'sell_order': sell_resp})
            return True
        elif buy_resp or sell_resp:
            # Check if order went through despite exchange returning an error
            last_totals = copy.deepcopy(self._exchanges.totals())
            self._exchanges.update_trading_balances()
            current_totals = self._exchanges.totals()
            base_cur_difference = abs(current_totals[base_currency] - last_totals[base_currency])
            quote_cur_difference = current_totals[self.quote_currency] - last_totals[self.quote_currency]
            # TODO: is 5% reasonable here? should it be lower?
            if base_cur_difference < order_volume * 0.05 and quote_cur_difference > 0:
                log.info('One order seemed to have failed but eventually went through',
                         event_name='arbitrage.place_order.delayed_success',
                         event_data={'buy_order': buy_resp, 'sell_order': sell_resp})
                return True
            else:
                log.warning('One order failed', event_name='arbitrage.place_order.partial_failure',
                            event_data={'buy_order': buy_resp, 'sell_order': sell_resp})
                raise RuntimeError('Place order failure')
                # TODO: Handle this better
        else:
            log.warning('Both orders failed', event_name='arbitrage.place_order.total_failure')
            raise RuntimeError('Place order failure')

    def arbitrage_table(self, base_currency: str):
        """Creates a table where rows represent to the exchange to buy from, and columns
        represent the exchange to sell to. The entry in each cell represents the percent profit/loss
        that would result from buying at the "buy" exchange and selling at the "sell" exchange.

        :returns: a dataframe representing the current arbitrage table
        """
        buy_exchanges = {x.name: x for x in self._exchanges.buy_exchanges(base_currency)}
        sell_exchanges = {x.name: x for x in self._exchanges.sell_exchanges(base_currency)}
        self._arbitrage_table = pd.DataFrame(index=buy_exchanges.keys(), columns=sell_exchanges.keys())
        self._find_best_arbitrage_opportunity(base_currency, update_table=True)
