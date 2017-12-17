import asyncio
import logging
import time
from contextlib import contextmanager
from functools import partial
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd
from requests.exceptions import RequestException, Timeout

from coinbitrage import bitlogging
from coinbitrage.exchanges.errors import ServerError
from coinbitrage.exchanges.manager import ExchangeManager
from coinbitrage.exchanges.mixins import SeparateTradingAccountMixin
from coinbitrage.settings import CURRENCIES, MAX_TRANSFER_FEE, ORDER_PRECISION
from coinbitrage.utils import RunEvery


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

    def run(self, make_transfers: bool = True):
        """Runs the program."""
        manage_balances = RunEvery(self._exchanges.manage_balances, delay=REBALANCE_FUNDS_EVERY)
        print_table = RunEvery(self._print_arbitrage_table, delay=PRINT_TABLE_EVERY)

        with self._exchanges.live_updates():
            try:
                while True:
                    if make_transfers:
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
        if not table.empty:
            table = table.applymap(lambda x: '{:.2f}%'.format(x*100) if x else '-')
            print()
            print(table)
            print()

    def _attempt_arbitrage(self):
        """Checks the arbitrage table to determine if there is an opportunity to profit,
        and if so executes the corresponding trades.
        """

        # TODO: consider balances (buy/sell power) in calculation of which is the "best" exchange
        buy_exchange = min(self._exchanges.valid_buys(), key=lambda x: x.ask(), default=None)
        sell_exchange = max(self._exchanges.valid_sells(), key=lambda x: x.bid(), default=None)

        if not (buy_exchange and sell_exchange) or buy_exchange.name == sell_exchange.name:
            return

        buy_price = buy_exchange.ask() * (1 + ORDER_PRECISION)
        sell_price = sell_exchange.bid() * (1 - ORDER_PRECISION)

        if sell_price < buy_price:
            return

        buy_tx_fee = buy_exchange.tx_fee(self.base_currency) * buy_price
        sell_tx_fee = sell_exchange.tx_fee(self.quote_currency)
        total_tx_fee = buy_tx_fee + sell_tx_fee

        # Amount of base currency that can be bought/sold at each exchange
        max_buy = self._exchanges.balances[buy_exchange.name][self.quote_currency] / buy_price
        max_sell = self._exchanges.balances[sell_exchange.name][self.base_currency]
        order_size = min(max_buy, max_sell)

        if order_size < CURRENCIES[self.base_currency]['order_size']:
            self._exchanges.update_active_exchanges()
            return

        expected_profit = order_size * (sell_price - buy_price)
        expected_profit -= total_tx_fee
        expected_pct_profit = expected_profit / buy_price

        buy_fee = buy_exchange.fee(self.base_currency, self.quote_currency)
        sell_fee = sell_exchange.fee(self.base_currency, self.quote_currency)
        expected_pct_profit -= (buy_fee + sell_fee)

        if expected_pct_profit > self._min_profit_threshold:
            log_msg = ('Arbitrage opportunity: '
                      '{buy_exchange} buy {volume} {base_currency} @ {buy_price}; '
                      '{sell_exchange} sell {volume} {quote_currency} @ {sell_price}; '
                      'profit: {expected_profit:.2f}%')
            event_data = {'buy_exchange': buy_exchange.name, 'sell_exchange': sell_exchange.name,
                          'volume': order_size, 'base_currency': self.base_currency, 'quote_currency': self.quote_currency,
                          'buy_price': buy_price, 'sell_price': sell_price, 'expected_profit': expected_pct_profit*100}
            log.info(log_msg, event_name='arbitrage.attempt', event_data=event_data)
            self._place_orders(buy_exchange, sell_exchange, buy_price, sell_price, order_size)

    def _arbitrage_profit_loss(self, buy_exchange, sell_exchange) -> Optional[float]:
        """Calculates the profit/loss of buying at one exchange and selling at another.

        :param buy_exchange: the exchange to buy from
        :param sell_exchange: the exchange to sell to
        """
        buy_ask = buy_exchange.ask()
        sell_bid = sell_exchange.bid()

        if buy_exchange.name == sell_exchange.name or not (buy_ask and sell_bid):
            return None

        return (sell_bid / buy_ask) - (1 + 2*ORDER_PRECISION)

    def _place_orders(self, buy_exchange, sell_exchange, buy_price: float, sell_price: float,
                      order_volume: float) -> bool:
        """Places buy and sell orders at the corresponding exchanges.

        :param buy_exchange: The name of the exchange to buy from
        :param sell_exchange: The name of the excahnge to sell at
        :param expected_profit: The percent profit that can be expected
        """

        async def place_order(exchange, *args, **kwargs):
            try:
                return exchange.wait_for_fill(exchange.limit_order(*args, **kwargs))
            except RequestException as e:
                log.error(e, event_name='place_order.error')
                return None

        futures = [
            place_order(buy_exchange, self.base_currency, 'buy', buy_price, order_volume, quote_currency=self.quote_currency),
            place_order(sell_exchange, self.base_currency, 'sell', sell_price, order_volume, quote_currency=self.quote_currency)
        ]
        buy_resp, sell_resp = tuple(self._loop.run_until_complete(asyncio.gather(*futures)))

        if buy_resp and sell_resp:
            log.info('Both orders placed successfully', event_name='arbitrage.place_order.success',
                     event_data={'buy_order': buy_resp, 'sell_order': sell_resp})
            self._exchanges.update_active_exchanges()
            return True
        elif any([buy_resp, sell_resp]):
            log.warning('One order failed', event_name='arbitrage.place_order.partial_failure',
                        event_data={'buy_order': buy_resp, 'sell_order': sell_resp})
            raise Exception
            # TODO: determine how to handle
        else:
            log.warning('Both orders failed', event_name='arbitrage.place_order.total_failure')
            raise Exception
            # TODO: determine how to handle

    def arbitrage_table(self) -> pd.DataFrame:
        """Creates a table where rows represent to the exchange to buy from, and columns
        represent the exchange to sell to. The entry in each cell represents the percent profit/loss
        that would result from buying at the "buy" exchange and selling at the "sell" exchange.

        :returns: a dataframe representing the current arbitrage table
        """
        buy_exchanges = {x.name: x for x in self._exchanges.valid_buys()}
        sell_exchanges = {x.name: x for x in self._exchanges.valid_sells()}
        table = pd.DataFrame(index=buy_exchanges.keys(), columns=sell_exchanges.keys())

        for buy_name, buy_exchg in buy_exchanges.items():
            for sell_name, sell_exchg in sell_exchanges.items():
                table.loc[buy_name, sell_name] = self._arbitrage_profit_loss(buy_exchg, sell_exchg)

        return table
