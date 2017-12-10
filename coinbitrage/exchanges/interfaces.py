from abc import ABC, abstractmethod, abstractstaticmethod, abstractproperty
from typing import Dict, List, Optional, Tuple, Union

from coinbitrage.exchanges.types import OHLC, Order, OrderBook, Timestamp, Trade
from coinbitrage.settings import DEFAULT_QUOTE_CURRENCY


class ExchangeBase(object):
    """
    """

    def pair(base_currency: str, quote_curency: str) -> str:
        """Combines the base and quote currencies into a currency pair that will
        be recognized by the exchange.

        :param base_currency:
        :param quote_currency:
        :returns: a currency pair recognizable by the exchange
        """
        raise NotImplementedError

    def unpair(currency_pair: str) -> Tuple[str, str]:
        """Separates a currency pair recognized by the exchange into its base and
        quote currencies.

        :param currency_pair:
        :returns: base, quote
        """
        raise NotImplementedError


class PublicMarketAPI(ExchangeBase):
    """Abstract base class for creating a wrapper around an exchange's API.

    Note: Implementing classes may choose to return more data than described here in
    their responses (e.g. average price, quote volume, etc.), but all must return
    AT LEAST the data described here.
    """

    def ohlc(self,
             base_currency: str,
             quote_currency: str = DEFAULT_QUOTE_CURRENCY,
             interval: int = 1,
             start: Optional[Timestamp] = None,
             end: Optional[Timestamp] = None) -> List[OHLC]:
        """Gets OHLC (candlestick) data from the exchange.

        :param base_currency:
        :param quote_currency:
        :param interval: the interval (in minutes) of the data to be fetched
        :param start: a timestamp representing the beginning of the requested data
        :param end: a timestamp representing the end of the requested data
        :returns: list of OHLC time periods
        """
        raise NotImplementedError

    def trades(self,
               base_currency: str,
               quote_currency: str = DEFAULT_QUOTE_CURRENCY,
               since: Optional[Timestamp] = None) -> List[Trade]:
        """Gets the most recent trades.

        :param base_currency:
        :param quote_currency:
        :param since: only return trades occuring after this timestamp
        :returns: list of the most recent trades

        """
        raise NotImplementedError

    def order_book(self,
                   base_currency: str,
                   quote_currency: str = DEFAULT_QUOTE_CURRENCY) -> OrderBook:
        """Gets the current order book.

        :param base_currency:
        :param quote_currency:
        :returns: the current order book
        """
        raise NotImplementedError


class PrivateExchangeAPI(ExchangeBase):
    """Abstract base class to provide additional functionality for private exchanges.
    Includes methods for placing, cancelling, and managing orders, as well as
    other account-related actions.
    """

    def fee(self,
            base_currency: str,
            quote_currency: str = DEFAULT_QUOTE_CURRENCY) -> float:
        """Gets the fee charged for buys and sells of the given currency pair. Fees should be
        cached in some manner, in order to avoid wasting lots of time requesting data that
        doesn't change very frequently.

        :param base_currency:
        :param quote_currency:
        :param use_cached: if False, query the exchange for the current value
        :returns: the fee charged for the given currency pair, as as percentage
        """
        raise NotImplementedError

    def limit_order(self,
                    base_currency: str,
                    side: str,
                    price: float,
                    volume: float,
                    quote_currency: str = DEFAULT_QUOTE_CURRENCY,
                    wait_for_fill: bool = False) -> Optional[Order]:
        """Places a limit order at the specified price.

        :param base_currency:
        :param side: whether or not the order is a 'buy' or a 'sell'
        :param price: the asking price of the order
        :param volume: how many units of the base currency to buy/sell
        :param quote_currency:
        :param wait_for_fill: if True, wait until the order is filled and return more complete info
                              (e.g. will include fill_price)
        :returns: info about the order that was placed if successful, None otherwise
        """
        raise NotImplementedError

    def cancel_order(self, order_id: str) -> bool:
        """Cancels the specified order.

        :param order_id: the ID of the order to cancel
        :returns: True if the order was successfully cancelled, False otherwise
        """
        raise NotImplementedError

    def deposit_address(self, currency: str) -> str:
        """Gets an address connected to this exchange that you can deposit funds
        to. This may create a new address or simply fetch an existing one.

        :param currency: the type of currency to get addresses for
        :returns: the address to deposit funds to
        """
        raise NotImplementedError

    def withdraw(self, currency: str, address: str, amount: float, **kwargs) -> bool:
        """Withdraws funds to the specified address.

        :param currency: the type of currency to withdraw
        :param address: the address to send the funds to
        :param amount: the amount of funds to withdraw
        :returns: True if the withdrawal succeeded, else False
        """
        raise NotImplementedError

    def balance(self) -> Dict[str, float]:
        """Returns the available balance of the given currency or currencies.

        :param currency: the currency or currencies to get the balance of
        :returns: the current balance if given a single currency, or a dict of the
                  form {currency: balance} if given a list of currencies
        """
        raise NotImplementedError

    def get_funds_from(self, from_exchange, currency: str, amount: float) -> bool:
        """Transfers funds to this exchange from the given exchange.

        :param from_exchange:
        :param currency:
        :param amount:
        """
        raise NotImplementedError


class WebsocketInterface(object):
    """Abstract base class to provide additional funcitonality for exchanges that support
    websockets.
    """

    @abstractproperty
    def running(self) -> bool:
        """
        """
        pass

    @abstractmethod
    def subscribe(self,
                  base_currency: str,
                  channel: str = 'ticker',
                  quote_currency: str = DEFAULT_QUOTE_CURRENCY):
        """Opens a connection to the websocket and subscribes to ticker updates for the
        given currency.

        :param base_currency:
        :param channel: the name of the channel to subscribe to
        :param quote_currency:
        """
        pass

    @abstractmethod
    def shutdown(self):
        """Stops the websocket stream."""
        pass
