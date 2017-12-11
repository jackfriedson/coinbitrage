from typing import Tuple

from bitex import Bittrex

from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.bitex import BitExRESTAdapter
from coinbitrage.exchanges.mixins import PeriodicRefreshMixin


class BittrexAPIAdapter(BitExRESTAdapter):
    _api_class = Bittrex
    _currency_map = {
        'BCH': 'BCC'
    }

    def __init__(self, *args, **kwargs):
        super(BittrexAPIAdapter, self).__init__(*args, **kwargs)
        self._inv_currency_map = {v: k for k, v in self._currency_map.items()}

    def pair(self, base_currency: str, quote_currency: str) -> str:
        base_currency = self._currency_map.get(base_currency, base_currency)
        quote_currency = self._currency_map.get(quote_currency, quote_currency)
        return '{}-{}'.format(quote_currency, base_currency)

    def unpair(self, currency_pair: str) -> Tuple[str, str]:
        currencies = currency_pair.split('-')
        base_currency = self._inv_currency_map.get(currencies[1], currencies[1])
        quote_currency = self._inv_currency_map.get(currencies[0], currencies[0])
        return base_currency, quote_currency


class BittrexClient(BaseExchangeClient, PeriodicRefreshMixin):
    name = 'bittrex'
    _api_class = BittrexAPIAdapter

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        PeriodicRefreshMixin.__init__(self, refresh_interval=1)
