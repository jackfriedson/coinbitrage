from typing import Tuple

from coinbitrage.exchanges.bitex import BitExFormatter
from coinbitrage.utils import format_floats


class BittrexFormatter(BitExFormatter):
    _currency_map = {
        'BCH': 'BCC',
        'USD': 'USDT'
    }

    def currencies(self, data):
        return {
            self.format(x['Currency'], inverse=True): {
                'tx_fee': x['TxFee'],
                'min_confirmations': x['MinConfirmation'],
                'is_active': x['IsActive'],
            } for x in data['result']
        }

    def order(self, data):
        d = data['result']
        base, quote = self.unpair(d['Exchange'])
        return {
            'id': d['OrderUuid'],
            'base_currency': base,
            'quote_currency': quote,
            'is_open': d['IsOpen'],
            'side': d['Type'].split('_')[-1].lower(),
            'cost': float(d['Price']),
            'avg_price': float(d['PricePerUnit']) if d['PricePerUnit'] else None,
            'fee': float(d['CommissionPaid']),
            'volume': float(d['Quantity']),
        }

    def order_book(self, data):
        return {
            'asks': {format_floats(x['Rate']): x['Quantity'] for x in data['sell']},
            'bids': {format_floats(x['Rate']): x['Quantity'] for x in data['buy']}
        }

    def deposit_address(self, data):
        return {'address': data}

    def pairs(self, data):
        return set([x['MarketName'] for x in data['result'] if x['IsActive']])

    def pair(self, base_currency: str, quote_currency: str) -> str:
        base = self.format(base_currency)
        quote = self.format(quote_currency)
        return f'{quote}-{base}'

    def unpair(self, currency_pair: str) -> Tuple[str, str]:
        quote, base = tuple(currency_pair.split('-'))
        base = self.format(base, inverse=True)
        quote = self.format(quote, inverse=True)
        return base, quote
