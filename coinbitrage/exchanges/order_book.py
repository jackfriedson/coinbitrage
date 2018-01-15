import time
from collections import defaultdict, namedtuple
from typing import Iterable, Optional

from pylimitbook.book import Book

from coinbitrage import bitlogging


log = bitlogging.getLogger(__name__)


OrderBookUpdate = namedtuple('OrderBookUpdate', ['pair', 'sequence', 'updates'])


class OrderBook(object):

    def __init__(self):
        self._books = {}
        self._next_sequence = {}
        self._pending_updates = defaultdict(dict)

    def update(self, full_update: OrderBookUpdate):
        pair, received_seq, entries = full_update
        expected_seq = self._next_sequence.get(pair)

        if expected_seq is None or received_seq == expected_seq:
            for entry in entries:
                getattr(self, entry['type'])(pair, entry)
            self._next_sequence[pair] = received_seq + 1
            self._apply_pending_updates(pair)
        else:
            assert received_seq > expected_seq
            self._pending_updates[pair][received_seq] = full_update
            log.warning('Received order book message {received_sequence} but the next expected one was {expected_sequence}',
                        event_name='order_book.sequence_error',
                        event_data={'received_sequence': received_seq, 'expected_sequence': expected_seq})

    def _apply_pending_updates(self, pair: str):
        pending = self._pending_updates[pair]
        if pending:
            next_update = pending.get(self._next_sequence[pair])
            while next_update:
                self.update(next_update)
                next_update = pending.get(self._next_sequence[pair])

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
