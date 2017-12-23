from coinbitrage.exchanges.bitex import BitExFormatter


class HitBtcFormatter(BitExFormatter):
    _currency_map = {
        'USDT': 'USD'
    }

    def currencies(self, data):
        return {
            self.format(cur['id'], inverse=True): {
                'min_confirmations': cur['payinConfirmations'],
                'is_active': cur['payinEnabled'] and cur['payoutEnabled'] and cur['transferEnabled'],
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
