import time
from typing import Iterable, Optional, Tuple, Union

import numpy as np

from coinbitrage.exchanges.bitex import BitExFormatter
from coinbitrage.exchanges.order_book import OrderBookUpdate
from coinbitrage.exchanges.wss import WebsocketMessage

from .symbol_ids import SYMBOL_IDS


class PoloniexFormatter(BitExFormatter):
    _currency_map = {
        'USD': 'USDT',
        'XLM': 'STR'
    }

    def __init__(self):
        super(PoloniexFormatter, self).__init__(pair_delimiter='_')

    def currencies(self, data):
        return {
            self.format(cur, inverse=True): {
                'tx_fee': info['txFee'],
                'min_confirmations': info['minConf'],
                'is_active': not info['disabled'] and not info['delisted']
            } for cur, info in data.items()
        }

    def order_trades(self, data):
        return {
            'base_currency': self.unpair(data[0]['currencyPair'])[0],
            'quote_currency': self.unpair(data[0]['currencyPair'])[1],
            'side': data[0]['type'],
            'avg_price': np.mean([float(trade['rate']) for trade in data]),
            'cost': sum([float(trade['total']) for trade in data]),
            'fee': sum([float(trade['fee']) for trade in data]),
            'volume': sum([float(trade['amount']) for trade in data])
        }

    def orders(self, data):
        def pair_orders(orders: list, pair: str = None):
            result = {
                order['orderNumber']: {
                    'side': order['type'],
                    'is_open': True,
                } for order in orders
            }
            if pair:
                base, quote = self.unpair(pair)
                for o in result.values():
                    o.update({'base_currency': base, 'quote_currency': quote})
            return result

        if isinstance(data, dict):
            result = {}
            for pair, orders in data.items():
                result.update(pair_orders(orders, pair=pair))
            return result
        return pair_orders(data)

    def pair(self, base_currency: str, quote_currency: str) -> str:
        return super(PoloniexFormatter, self).pair(quote_currency, base_currency)

    def unpair(self, currency_pair: str) -> Tuple[str, str]:
        quote, base = super(PoloniexFormatter, self).unpair(currency_pair)
        return base, quote


class PoloniexWebsocketFormatter(PoloniexFormatter):
    channel_names = {
        1001: 'trollbox',
        1002: 'ticker',
        1003: 'stats',
        1010: 'heartbeat',
    }
    channel_ids = {v: k for k, v in channel_names.items()}

    def websocket_message(self, msg: list) -> Optional[WebsocketMessage]:
        channel = self.get_channel_name(msg[0])
        formatter = getattr(self, channel)

        formatted = formatter(msg)
        if not formatted:
            return None

        pair, data = formatted
        return WebsocketMessage(channel, pair, data)

    def get_channel_id(self, channel: str, pair: str) -> Union[int, str]:
        if channel == 'order_book':
            return pair
        return self.channel_ids[channel]

    def get_channel_name(self, channel_id: str) -> str:
        if channel_id in SYMBOL_IDS:
            return 'order_book'
        return self.channel_names[int(channel_id)]

    def ticker(self, msg: list) -> Optional[Tuple[str, dict]]:
        if len(msg) <= 2:
            return None

        data = msg[2]
        pair = SYMBOL_IDS[data[0]]
        bid_ask = {
            'bid': float(data[2]),
            'ask': float(data[3]),
            'recv_time': time.time(),
        }
        return pair, bid_ask

    def order_book(self, msg: list) -> Optional[Tuple[str, OrderBookUpdate]]:
        pair = SYMBOL_IDS[msg[0]]
        type_map = {
            'i': 'initialize',
            'o': 'order',
            't': 'trade',
        }

        def format_book_entry(entry: list) -> dict:
            entry_type = type_map[entry[0]]

            if entry_type == 'initialize':
                book = entry[1]['orderBook']
                data = {
                    'asks': book[0],
                    'bids': book[1]
                }
            elif entry_type == 'order':
                data = {
                    'side': 'bid' if entry[1] == 1 else 'ask',
                    'price': entry[2],
                    'quantity': entry[3]
                }
            elif entry_type == 'trade':
                data = {
                    'side': 'buy' if entry[2] == 1 else 'sell',
                    'price': entry[3],
                    'quantity': entry[4],
                    'time': entry[5],
                }

            data['type'] = entry_type
            return data

        return pair, OrderBookUpdate(pair, msg[1], (format_book_entry(entry) for entry in msg[2]))

    def trollbox(self, msg: list) -> Optional[Tuple[str, dict]]:
        return None

    def heartbeat(self, msg: list) -> Optional[Tuple[str, dict]]:
        return None
