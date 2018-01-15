import time
from collections import defaultdict
from typing import Optional

from pylimitbook.book import Book


class OrderBook(object):

    def __init__(self):
        self._books = {}

    def update(self, updates: list):
        for update in updates:
            getattr(self, update['type'])(update['pair'], update['data'])

    def initialize(self, pair: str, data: dict):
        self._books[pair] = Book()

        for price, quantity in data['bids'].items():
            self._books[pair].bid_split(*self._format_args(pair, price, quantity))

        for price, quantity in data['asks'].items():
            self._books[pair].ask_split(*self._format_args(pair, price, quantity))

    def order(self, pair: str, data: dict):
        try:
            book_add_fn = self._books[pair].bid_split if data['side'] == 'bid' else self._books[pair].ask_split
            book_add_fn(*self._format_args(pair, data['price'], data['quantity']))
        except Exception as e:
            print(e.tb)

    def trade(self, pair: str, data: dict):
        pass

    @staticmethod
    def _format_args(pair, price, quantity):
        return pair, str(price), float(quantity), str(price), time.time()

    def best_bid(self, pair: str) -> Optional[dict]:
        if pair not in self._books:
            return None

        book = self._books[pair]
        return {
            'bid': book.bids.max(as_float=True),
            'bid_size': book.bids.get_price(book.bids.max()).volume,
            'recv_time': book.last_timestamp
        }

    def best_ask(self, pair: str) -> Optional[dict]:
        if pair not in self._books:
            return None

        book = self._books[pair]
        return {
            'ask': book.asks.min(as_float=True),
            'ask_size': book.asks.get_price(book.asks.min()).volume,
            'recv_time': book.last_timestamp
        }
