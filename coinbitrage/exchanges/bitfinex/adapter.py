from bitex import Bitfinex
from bitex.api.WSS import BitfinexWSS

from coinbitrage import settings
from coinbitrage.exchanges.bitex import BitExAPIAdapter, BitExWSSAdapter


class BitfinexAPIAdapter(BitExAPIAdapter, BitExWSSAdapter):
    formatters = {
        'ticker': lambda msg: {
            'time': msg[2][1],
            'pair': msg[1],
            'bid': float(msg[2][0][0]),
            'ask': float(msg[2][0][2])
        }
    }

    def __init__(self, key_file: str):
        super(BitfinexAPIAdapter, self).__init__(api=Bitfinex(key_file=key_file), websocket=BitfinexWSS())

    @staticmethod
    def currency_pair(base_currency: str, quote_currency: str) -> str:
        return base_currency + quote_currency

    def subscribe(self,
                  base_currency: str,
                  channel: str = 'ticker',
                  quote_currency: str = settings.DEFAULT_QUOTE_CURRENCY):
        super(BitfinexAPIAdapter, self).subscribe(base_currency, channel, quote_currency)

        pair = self.currency_pair(base_currency, quote_currency)
        if channel == 'ticker':
            self._websocket.ticker(pair)
