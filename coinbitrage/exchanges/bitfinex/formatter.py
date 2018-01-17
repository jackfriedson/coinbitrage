from typing import Iterable, Optional, Tuple, Union

from coinbitrage.exchanges.bitex import BitExFormatter
from coinbitrage.exchanges.order_book import OrderBookUpdate
from coinbitrage.exchanges.wss import WebsocketMessage
from coinbitrage.utils import format_floats


class BitfinexFormatter(BitExFormatter):

    def pair(self, base_currency: str, quote_currency: str) -> str:
        return super(BitfinexFormatter, self).pair(base_currency, quote_currency).lower()

    def unpair(self, currency_pair: str) -> Tuple[str, str]:
        return super(BitfinexFormatter, self).unpair(currency_pair.upper())

    def deposit_address(self, data) -> dict:
        data.pop('result')
        data.pop('method')
        data.pop('currency')
        return data

    def balance(self, data) -> dict:
        return {
            bal['currency'].upper(): float(bal['available'])
            for bal in data if bal['type'] == 'exchange'
        }

    def withdraw(self, data) -> dict:
        return data[0]

    def order(self, data) -> dict:
        base, quote = self.unpair(data['symbol'])
        return {
            'base_currency': base,
            'quote_currency': quote,
            'is_open': data['is_live'],
            'side': data['side'],
            'avg_price': float(data['avg_execution_price']),
            'volume': float(data['original_amount']),
        }


class BitfinexWebsocketFormatter(BitfinexFormatter):
    hitbtc_channel_names = {
        'order_book': 'book',
        'trades': 'trades',
        'ticker': 'ticker',
    }
    coinbitrage_channel_names = {v: k for k, v in hitbtc_channel_names.items()}

    def __init__(self, *args, **kwargs):
        super(BitfinexWebsocketFormatter, self).__init__(*args, **kwargs)
        self._channel_ids = {}

    def websocket_message(self, msg: Union[list, dict]) -> Optional[WebsocketMessage]:
        if isinstance(msg, dict):
            if msg['event'] == 'subscribed':
                chan_name = self.coinbitrage_channel_names[msg['channel']]
                self._channel_ids[msg['chanId']] = (chan_name, msg['pair'].lower())
            return None

        channel, pair = self._channel_ids.get(msg[0])
        data = msg[1]
        if data == 'hb':
            return None

        data = getattr(self, channel)(data)

        if channel == 'order_book':
            data = OrderBookUpdate(pair, None, data)

        return WebsocketMessage(channel, pair, data)

    def ticker(self, data: list):
        return {
            'bid': float(data[0][0]),
            'ask': float(data[0][2]),
            'time': data[1],
        }

    def order_book(self, data: list) -> Iterable[dict]:
        if len(data) == 3:
            price, count, amount = tuple(data)
            return [{
                'type': 'order',
                'side': 'bid' if amount > 0 else 'ask',
                'price': format_floats(price),
                'quantity': 0 if count == 0 else abs(amount)
            }]
        else:
            asks = {}
            bids = {}
            for entry in data:
                price, count, amount = tuple(entry)
                side = bids if amount > 0 else asks
                side[format_floats(price)] = abs(amount)
            return [{
                'type': 'initialize',
                'asks': asks,
                'bids': bids,
            }]
