from coinbitrage.exchanges.bitex import BitExFormatter


class BitfinexFormatter(BitExFormatter):

    def deposit_address(self, data):
        data.pop('result')
        data.pop('method')
        data.pop('currency')
        return data
