import time
from collections import defaultdict, namedtuple
from typing import Iterable, List, Optional, Tuple

from bintrees import FastRBTree
from pylimitbook.book import Book
from pylimitbook.settings import PRICE_PRECISION

from coinbitrage import bitlogging
from coinbitrage.exchanges.errors import OrderBookUpdateError


log = bitlogging.getLogger(__name__)


OrderBookUpdate = namedtuple('OrderBookUpdate', ['pair', 'sequence', 'updates'])


class OrderBook(object):

    def __init__(self):
        self._initialized = {}
        self._books = {}
        self._next_sequence = {}
        self._pending_updates = defaultdict(dict)

    def update(self, full_update: OrderBookUpdate):
        pair, received_seq, entries = full_update
        expected_seq = self._next_sequence.get(pair)

        if expected_seq is None or received_seq == expected_seq:
            for entry in entries:
                getattr(self, entry['type'])(pair, entry)
            if received_seq is not None:
                self._next_sequence[pair] = received_seq + 1
                # self._apply_pending_updates(pair)
        else:
            log.error('Received order book message {received_sequence} but the next expected one was {expected_sequence}',
                        event_name='order_book.sequence_error',
                        event_data={'received_sequence': received_seq, 'expected_sequence': expected_seq})
            raise OrderBookUpdateError('Recieved messages out of order')
            # assert received_seq > expected_seq
            # self._pending_updates[pair][received_seq] = full_update


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

        self._initialized[pair] = True

    def order(self, pair: str, data: dict):
        book_add_fn = self._books[pair].bid_split if data['side'] == 'bid' else self._books[pair].ask_split
        book_add_fn(*self._format_args(pair, data['price'], data['quantity']))

    def trade(self, pair: str, data: dict):
        pass

    @staticmethod
    def _format_args(pair: str, price: float, quantity: float):
        return pair, str(price), float(quantity), str(price), time.time()

    def _get_book_side(self, is_bid: bool, pair: str, max_volume: float = None) -> Iterable[Tuple[float, float]]:
        tree = self._books[pair].bids.price_tree if is_bid else self._books[pair].asks.price_tree
        if max_volume is None:
            ret = tree.items(is_bid)
        else:
            vol_remaining = max_volume
            for price, orders in tree.items(is_bid):
                vol_remaining -= orders.volume
                if vol_remaining <= 0:
                    break
            start = None if not is_bid else price
            end = price+1 if not is_bid else None
            ret = tree.item_slice(start, end, is_bid)

        return ((self._format_price(price), orders.volume) for price, orders in ret)

    def get_bids(self, pair: str, max_volume: float) -> Iterable[Tuple[float, float]]:
        return self._get_book_side(True, pair, max_volume)

    def get_asks(self, pair: str, max_volume: float = None) -> Iterable[Tuple[float, float]]:
        return self._get_book_side(False, pair, max_volume)

    def updated_recently(self, pair: str, seconds: int) -> bool:
        last_ts = self._books[pair].last_timestamp
        if last_ts is None or not self.initialized(pair):
            return False
        return time.time() - last_ts <= seconds

    def best_bid(self, pair: str) -> float:
        if not self._initialized.get(pair, False):
            raise RuntimeError(f'{pair} not initialized')
        bid_tree = self._books[pair].bids.price_tree
        return self._format_price(bid_tree.max_key())

    def best_ask(self, pair: str) -> float:
        if not self._initialized.get(pair, False):
            raise RuntimeError(f'{pair} not initialized')
        ask_tree = self._books[pair].asks.price_tree
        return self._format_price(ask_tree.min_key())

    def initialized(self, pair: str) -> bool:
        return self._initialized.get(pair, False)

    @staticmethod
    def _format_price(price: int) -> float:
        return price / 10**PRICE_PRECISION
