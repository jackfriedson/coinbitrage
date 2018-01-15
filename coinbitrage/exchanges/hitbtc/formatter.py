import time
from typing import Optional, Tuple

import dateutil.parser

from coinbitrage.exchanges.bitex import BitExFormatter
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

        formatter = getattr(self, msg['method'])
        return WebsocketMessage(msg['method'], msg['params']['symbol'], formatter(msg['params']))

    def ticker(self, data: dict) -> dict:
        return {
            'bid': float(data['bid']),
            'ask': float(data['ask']),
            'time': dateutil.parser.parse(data['timestamp']).timestamp()
        }

    def order_book(self, data: dict) -> dict:
        return data
