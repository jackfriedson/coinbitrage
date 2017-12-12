import time
from typing import Dict, List, Union

from bitex import Kraken

from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.bitex import BitExRESTAdapter
from coinbitrage.exchanges.mixins import PeriodicRefreshMixin


KRAKEN_API_CALL_RATE = 3.


class KrakenAPIAdapter(BitExRESTAdapter):
    _api_class = Kraken
    _currency_map = {
        'BTC': 'XXBT',
        'ETH': 'XETH',
        'USDT': 'ZUSD',
    }

    def deposit_address(self, currency: str) -> str:
        if currency == 'BTC':
            method = 'Bitcoin'
        elif currency == 'ETH':
            method = 'Ether (Hex)'
        elif currency == 'USDT':
            method = 'Tether USD'
        else:
            raise NotImplementedError('Deposit address not implemented for {}'.format(currency))

        currency = self.fmt_currency(currency)
        resp = self._api.deposit_address(asset=currency, method=method)
        resp.raise_for_status()
        addr = resp.json()['result'][0]['address']
        return addr


class KrakenClient(BaseExchangeClient, PeriodicRefreshMixin):
    name = 'kraken'
    _api_class = KrakenAPIAdapter

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        PeriodicRefreshMixin.__init__(self, refresh_interval=1)


