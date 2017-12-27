import asyncio
import logging
import time
from contextlib import contextmanager
from functools import partial
from itertools import product
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import pandas as pd
from requests.exceptions import RequestException, Timeout

from coinbitrage import bitlogging
from coinbitrage.exchanges.errors import ServerError
from coinbitrage.exchanges.manager import ExchangeManager
from coinbitrage.exchanges.mixins import SeparateTradingAccountMixin
from coinbitrage.settings import CURRENCIES, ORDER_PRECISION
from coinbitrage.utils import RunEvery, format_float


REBALANCE_FUNDS_EVERY = 60 * 5  # Rebalance funds every 5 minutes
PRINT_TABLE_EVERY = 60 * 1  # Print table every minute


log = bitlogging.getLogger(__name__)


class ArbitrageEngine(object):

    def __init__(self,
                 exchanges: List[str],
                 base_currency: Union[str, List[str]],
                 quote_currency: str,
                 min_profit: float = 0.,
                 **kwargs):
        self.base_currencies = base_currency if isinstance(base_currency, list) else [base_currency]
        self.quote_currency = quote_currency
        self._loop = asyncio.get_event_loop()
        self._exchanges = ExchangeManager(exchanges, base_currency, quote_currency, loop=self._loop, **kwargs)
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
        # TODO: keep track of actual arbitrage values and just print those, instead of
        # doing a separate computation here

        for currency in self.base_currencies:
            table = self.arbitrage_table(currency)
            if not table.empty:
                table = table.applymap(lambda x: '{:.2f}%'.format(x*100) if x is not None else '-')
                print()
                print(currency)
                print(table)
                print()

    def _find_best_arbitrage_opportunity(self, base_currency: str):
        best_opportunity = None

        for buy_exchange, sell_exchange in product(self._exchanges.valid_buys(base_currency), self._exchanges.valid_sells(base_currency)):
            if buy_exchange.name == sell_exchange.name:
                continue

            buy_price = buy_exchange.ask(base_currency) * (1 + ORDER_PRECISION)
            sell_price = sell_exchange.bid(base_currency) * (1 - ORDER_PRECISION)

            if base_currency == 'LTC':
                if buy_exchange.name == 'kraken':
                    buy_price = float(format_float(buy_price, 2))
                elif sell_exchange.name == 'kraken':
                    sell_price = float(format_float(sell_price, 2))

            if sell_price < buy_price:
                continue

            # Amount of base currency that can be bought/sold at each exchange
            max_buy = self._exchanges.balances()[buy_exchange.name][self.quote_currency] / buy_price
            max_sell = self._exchanges.balances()[sell_exchange.name][base_currency]
            order_size = min(max_buy, max_sell)

            if order_size < CURRENCIES[base_currency]['order_size']:
                continue

            gross_percent_profit = (sell_price / buy_price) - 1
            gross_profit = gross_percent_profit * buy_price * order_size

            buy_fee = order_size * buy_price * buy_exchange.fee(base_currency, self.quote_currency)
            sell_fee = order_size * sell_price * sell_exchange.fee(base_currency, self.quote_currency)

            buy_tx_fee = buy_exchange.tx_fee(base_currency) * buy_price
            # sell_tx_fee = sell_exchange.tx_fee(self.quote_currency)
            sell_tx_fee = 0.
            total_tx_fee = buy_tx_fee + sell_tx_fee

            total_fees = buy_fee + sell_fee + total_tx_fee
            net_profit = gross_profit - total_fees
            net_pct_profit = net_profit / buy_price

            if best_opportunity is None or net_profit > best_opportunity['net_profit']:
                # Mostly for logging/debugging
                best_opportunity = {
                    'base_currency': base_currency,
                    'quote_currency': self.quote_currency,
                    'buy_exchange': buy_exchange.name,
                    'buy_price': buy_price,
                    'sell_exchange': sell_exchange.name,
                    'sell_price': sell_price,
                    'gross_percent_profit': gross_percent_profit,
                    'net_pct_profit': net_pct_profit,
                    'net_profit': net_profit,
                    'gross_profit': gross_profit,
                    'order_size': order_size,
                    'total_tx_fee': total_tx_fee,
                    'total_fees': total_fees,
                    'buy_tx_fee': buy_tx_fee,
                    'sell_tx_fee': sell_tx_fee,
                    'buy_fee': buy_fee,
                    'sell_fee': sell_fee,
                    'max_buy': max_buy,
                    'max_sell': max_sell
                }

        return best_opportunity

    def _attempt_arbitrage(self):
        """Checks the arbitrage table to determine if there is an opportunity to profit,
        and if so executes the corresponding trades.
        """
        for currency in self.base_currencies:
            opportunity = self._find_best_arbitrage_opportunity(currency)
            if not opportunity:
                return

            if opportunity['net_pct_profit'] > self._min_profit_threshold:
                self._execute_arbitrage(**opportunity)

            # log.debug('', event_name='arbitrage.debug', event_data=opportunity)

    def _execute_arbitrage(self,
                           base_currency: str,
                           quote_currency: str,
                           buy_exchange: str,
                           sell_exchange: str,
                           buy_price: float,
                           sell_price: float,
                           order_size: float,
                           total_tx_fee: float,
                           net_pct_profit: float, **kwargs):
        buy_exchange = self._exchanges.get(buy_exchange)
        sell_exchange = self._exchanges.get(sell_exchange)

        log_msg = ('Arbitrage opportunity: '
                   '{buy_exchange} buy {volume} {base_currency} @ {buy_price}; '
                   '{sell_exchange} sell {volume} {base_currency} @ {sell_price}; '
                   'profit: {profit:.2f}%')
        event_data = {'buy_exchange': buy_exchange.name, 'sell_exchange': sell_exchange.name,
                      'volume': order_size, 'base_currency': base_currency, 'quote_currency': quote_currency,
                      'buy_price': buy_price, 'sell_price': sell_price, 'profit': net_pct_profit*100}
        event_data.update(kwargs)
        log.info(log_msg, event_name='arbitrage.attempt', event_data=event_data)

        if self._place_orders(base_currency, quote_currency, buy_exchange, sell_exchange, buy_price, sell_price, order_size):
            self._exchanges.add_order('buy', buy_exchange.name)
            self._exchanges.add_order('sell', sell_exchange.name)
            self._exchanges.tx_credits += total_tx_fee

    def _arbitrage_profit_loss(self, buy_exchange, sell_exchange, base_currency) -> Optional[float]:
        """Calculates the profit/loss of buying at one exchange and selling at another.

        :param buy_exchange: the exchange to buy from
        :param sell_exchange: the exchange to sell to
        """
        buy_ask = buy_exchange.ask(base_currency)
        sell_bid = sell_exchange.bid(base_currency)

        if buy_exchange.name == sell_exchange.name or not (buy_ask and sell_bid):
            return None

        return (sell_bid / buy_ask) - (1 + 2*ORDER_PRECISION)

    def _place_orders(self,
                      base_currency: str,
                      quote_currency: str,
                      buy_exchange,
                      sell_exchange,
                      buy_price: float,
                      sell_price: float,
                      order_volume: float) -> bool:
        """Places buy and sell orders at the corresponding exchanges.

        :param buy_exchange: The name of the exchange to buy from
        :param sell_exchange: The name of the excahnge to sell at
        :param expected_profit: The percent profit that can be expected
        """

        async def place_order(exchange, *args, **kwargs):
            try:
                return await exchange.wait_for_fill(exchange.limit_order(*args, **kwargs), do_async=True)
            except RequestException as e:
                log.error(e, event_name='place_order.error')
                return None

        futures = [
            place_order(buy_exchange, base_currency, 'buy', buy_price, order_volume, quote_currency=quote_currency),
            place_order(sell_exchange, base_currency, 'sell', sell_price, order_volume, quote_currency=quote_currency)
        ]
        buy_resp, sell_resp = tuple(self._loop.run_until_complete(asyncio.gather(*futures)))

        if buy_resp and sell_resp:
            log.info('Both orders placed successfully', event_name='arbitrage.place_order.success',
                     event_data={'buy_order': buy_resp, 'sell_order': sell_resp})
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

    def arbitrage_table(self, base_currency: str) -> pd.DataFrame:
        """Creates a table where rows represent to the exchange to buy from, and columns
        represent the exchange to sell to. The entry in each cell represents the percent profit/loss
        that would result from buying at the "buy" exchange and selling at the "sell" exchange.

        :returns: a dataframe representing the current arbitrage table
        """
        buy_exchanges = {x.name: x for x in self._exchanges.valid_buys(base_currency)}
        sell_exchanges = {x.name: x for x in self._exchanges.valid_sells(base_currency)}
        table = pd.DataFrame(index=buy_exchanges.keys(), columns=sell_exchanges.keys())

        for buy_name, buy_exchg in buy_exchanges.items():
            for sell_name, sell_exchg in sell_exchanges.items():
                table.loc[buy_name, sell_name] = self._arbitrage_profit_loss(buy_exchg, sell_exchg, base_currency)

        return table
