from coinbitrage.exchanges.bitex import BitExFormatter


class KrakenFormatter(BitExFormatter):
    _currency_map = {
        'BTC': 'XXBT',
        'ETH': 'XETH',
        'LTC': 'XLTC',
        'USD': 'ZUSD',
    }

    def pair(self, base_currency: str, quote_currency: str) -> str:
        if base_currency in ['BCH', 'EOS', 'GNO']:
            quote_currency = 'XBT' if quote_currency == 'BTC' else quote_currency
            return base_currency + quote_currency
        return super(KrakenFormatter, self).pair(base_currency, quote_currency)

    def _format_orders(self, orders: dict, is_open: bool):
        return {
            order_id: {
                'base_currency': self.unpair(info['descr']['pair'])[0],
                'quote_currency': self.unpair(info['descr']['pair'])[1],
                'is_open': is_open,
                'side': info['descr']['type'],
                'cost': float(info['cost']),
                'avg_price': float(info['price']),
                'fee': float(info['fee']),
                'volume': float(info['vol']),
            } for order_id, info in orders.items()
        }

    def closed_orders(self, data):
        return self._format_orders(data['result']['closed'], False)

    def open_orders(self, data):
        return self._format_orders(data['result']['open'], True)

    def pairs(self, data):
        return data['result']

    def deposit_address(self, data):
        return data['result'][0]['address']
