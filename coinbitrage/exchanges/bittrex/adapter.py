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

    def pair(self, base_currency: str, quote_currency: str) -> str:
        base_currency = self.fmt_currency(base_currency)
        quote_currency = self.fmt_currency(quote_currency)
        return '{}-{}'.format(quote_currency, base_currency)

    def unpair(self, currency_pair: str) -> Tuple[str, str]:
        currencies = currency_pair.split('-')
        base_currency = self.fmt_currency(currencies[1], inverse=True)
        quote_currency = self.fmt_currency(currencies[0], inverse=True)
        return base_currency, quote_currency


class BittrexClient(BaseExchangeClient, PeriodicRefreshMixin):
    name = 'bittrex'
    _api_class = BittrexAPIAdapter

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        PeriodicRefreshMixin.__init__(self, refresh_interval=1)
