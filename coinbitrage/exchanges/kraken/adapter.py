import time
from typing import Dict, List, Union

from bitex import Kraken

from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.bitex import BitExRESTAdapter
from coinbitrage.exchanges.mixins import PeriodicRefreshMixin


KRAKEN_API_CALL_RATE = 3.
CURRENCY_MAP = {
    'BTC': 'XXBT',
    'ETH': 'XETH',
    'USD': 'ZUSD',
}


class KrakenAPIAdapter(BitExRESTAdapter):
    _api_class = Kraken

    _formatters = {
        'ticker': lambda x: {
            'bid': float(x[0]),
            'ask': float(x[1]),
            'time': time.time(),
        }
    }

    def __init__(self, key_file: str):
        super(KrakenAPIAdapter, self).__init__(key_file=key_file)

    def deposit_address(self, currency: str) -> str:
        if currency == 'BTC':
            method = 'Bitcoin'
        elif currency == 'ETH':
            method = 'Ether (Hex)'
        else:
            raise NotImplementedError

        currency = CURRENCY_MAP[currency]
        resp = self._api.deposit_address(asset=currency, method=method)
        resp.raise_for_status()
        addr = resp.json()['result'][0]['address']
        return addr

    def fee(self, currency: str):
        # TODO: actually implement
        return 0.0025

    def withdraw(self, currency: str, address: str, amount: float, **kwargs) -> bool:
        pass

    def pair(self, base_currency: str, quote_currency: str):
        base_currency = CURRENCY_MAP.get(base_currency, base_currency)
        quote_currency = CURRENCY_MAP.get(quote_currency, quote_currency)
        return base_currency + quote_currency


class KrakenClient(BaseExchangeClient):
    name = 'kraken'
    _api_class = KrakenAPIAdapter

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)


