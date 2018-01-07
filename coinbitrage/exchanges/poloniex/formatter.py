from typing import Tuple

import numpy as np

from coinbitrage.exchanges.bitex import BitExFormatter


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
