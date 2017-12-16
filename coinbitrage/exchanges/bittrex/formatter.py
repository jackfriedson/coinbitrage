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

    def pair(self, base_currency: str, quote_currency: str) -> str:
        base = self.format(base_currency)
        quote = self.format(quote_currency)
        return '{}-{}'.format(quote, base)

    def unpair(self, currency_pair: str) -> Tuple[str, str]:
        quote, base = tuple(currency_pair.split('-'))
        base = self.format(base, inverse=True)
        quote = self.format(quote, inverse=True)
        return base, quote
