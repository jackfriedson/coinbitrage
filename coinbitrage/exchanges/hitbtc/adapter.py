
from bitex import HitBtc

from coinbitrage.exchanges.bitex import BitExRESTAdapter


class HitBTCAdapter(BitExRESTAdapter):

    _formatters = {}

    def __init__(self, name: str, key_file: str):
        api = HitBtc(key_file=key_file)
        super(HitBTCAdapter, self).__init__(name, api)

    @staticmethod
    def currency_pair(base_currency: str, quote_currency: str):
        return base_currency + quote_currency
