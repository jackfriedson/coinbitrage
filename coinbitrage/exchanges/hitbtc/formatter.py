import itertools
import time
from typing import Iterable, Optional, Tuple

import dateutil.parser

from coinbitrage.exchanges.bitex import BitExFormatter
from coinbitrage.exchanges.order_book import OrderBookUpdate
from coinbitrage.exchanges.wss import WebsocketMessage


class HitBtcFormatter(BitExFormatter):

    def pair(self, base_currency: str, quote_currency: str) -> str:
        if base_currency == 'XRP' and quote_currency == 'USD':
            return 'XRPUSDT'
        return super(HitBtcFormatter, self).pair(base_currency, quote_currency)

    def balance(self, data):
        def inv_map(cur):
            if cur == 'USDT':
                return 'USD'
            return cur
        return {inv_map(k): v for k, v in super(HitBtcFormatter, self).balance(data).items()}

    def currencies(self, data):
        return {
            self.format(cur['id'], inverse=True): {
                'min_confirmations': cur['payinConfirmations'],
                'deposits_active': cur['payinEnabled'] and cur['transferEnabled'],
                'withdrawals_active': cur['payoutEnabled'] and cur['transferEnabled'],
            } for cur in data
        }

    def pairs(self, data):
        return {pair['id']: pair for pair in data}

    def order(self, data):
        base, quote = self.unpair(data['symbol'])
        return {
            'id': data['clientOrderId'],
            'base_currency': base,
            'quote_currency': quote,
            'is_open': data['status'] == 'new',
            'side': data['side'],
            'volume': float(data['quantity']),
        }

    def order_history(self, data):
        return [self.order(order_data) for order_data in data]


class HitBtcWebsocketFormatter(HitBtcFormatter):

    def websocket_message(self, msg: dict) -> Optional[WebsocketMessage]:
        if 'method' not in msg:
            return None

        channel = msg['method']
        formatter = getattr(self, channel)

        if channel in ['snapshotOrderbook', 'updateOrderbook']:
            channel = 'order_book'

        return WebsocketMessage(channel, msg['params']['symbol'], formatter(msg['params']))

    def ticker(self, data: dict) -> dict:
        return {
            'bid': float(data['bid']),
            'ask': float(data['ask']),
            'time': dateutil.parser.parse(data['timestamp']).timestamp()
        }

    def snapshotOrderbook(self, data: dict) -> OrderBookUpdate:
        updates = [{
            'type': 'initialize',
            'asks': {entry['price']: entry['size'] for entry in data['ask']},
            'bids': {entry['price']: entry['size'] for entry in data['bid']}
        }]
        return OrderBookUpdate(data['symbol'], data['sequence'], updates)

    def updateOrderbook(self, data: dict) -> OrderBookUpdate:
        def format_book_entry(entry: dict, side: str) -> dict:
            return {
                'type': 'order',
                'side': side,
                'price': entry['price'],
                'quantity': entry['size'],
                'time': time.time()
            }

        asks = (format_book_entry(entry, 'ask') for entry in data['ask'])
        bids = (format_book_entry(entry, 'bid') for entry in data['bid'])
        return OrderBookUpdate(data['symbol'], data['sequence'], itertools.chain(asks, bids))
