from coinbitrage.exchanges.bitex import BitExFormatter


class KrakenFormatter(BitExFormatter):
    _currency_map = {
        'BTC': 'XXBT',
        'ETH': 'XETH',
        'USD': 'ZUSD',
    }

    def pairs(self, data):
        return set(data['result'].keys())

    def deposit_address(self, data):
        return data['result'][0]['address']
