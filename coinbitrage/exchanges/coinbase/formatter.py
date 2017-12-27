from coinbitrage.exchanges.bitex import BitExFormatter


class CoinbaseFormatter(BitExFormatter):

    def __init__(self):
        super(CoinbaseFormatter, self).__init__(pair_delimiter='-')

    def pairs(self, data):
        return {pair['id'] for pair in data if pair['status'] == 'online'}
