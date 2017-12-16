
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
