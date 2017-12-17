from typing import Tuple

from coinbitrage.exchanges.bitex import BitExFormatter


class BittrexFormatter(BitExFormatter):
    _currency_map = {
        'BCH': 'BCC'
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
            'side': 'buy' if 'buy' in d['OrderType'].lower() else 'sell',
            'cost': float(d['Price']),
            'avg_price': float(d['PricePerUnit']),
            'fee': float(d['CommissionPaid']),
            'volume': float(d['Quantity']),
        }

    def pairs(self, data):
        return set([x['MarketName'] for x in data['result'] if x['IsActive']])

    def pair(self, base_currency: str, quote_currency: str) -> str:
        base = self.format(base_currency)
        quote = self.format(quote_currency)
        return '{}-{}'.format(quote, base)

    def unpair(self, currency_pair: str) -> Tuple[str, str]:
        quote, base = tuple(currency_pair.split('-'))
        base = self.format(base, inverse=True)
        quote = self.format(quote, inverse=True)
        return base, quote
