from typing import Tuple

from coinbitrage.exchanges.bitex import BitExFormatter


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

    def ticker(self, data):
        return {
            'bid': float(data[0][1]),
            'ask': float(data[0][3]),
            'time': data[1],
        }

    def order_book(self, data):
        return data
