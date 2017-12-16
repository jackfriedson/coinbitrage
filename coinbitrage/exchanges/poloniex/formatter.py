from typing import Tuple

from coinbitrage.exchanges.bitex import BitExFormatter


class PoloniexFormatter(BitExFormatter):
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

    def pair(self, base_currency: str, quote_currency: str) -> str:
        return super(PoloniexFormatter, self).pair(quote_currency, base_currency)

    def unpair(self, currency_pair: str) -> Tuple[str, str]:
        quote, base = super(PoloniexFormatter, self).unpair(currency_pair)
        return base, quote
