from coinbitrage.exchanges.bitex import BitExFormatter


class KrakenFormatter(BitExFormatter):
    _currency_map = {
        'BTC': 'XXBT',
        'ETH': 'XETH',
        'USD': 'ZUSD',
    }
