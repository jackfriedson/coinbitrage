from typing import Tuple

from bitex import Bittrex

from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.bitex import BitExRESTAdapter
from coinbitrage.exchanges.mixins import PeriodicRefreshMixin


_currency_map = {
    'BCH': 'BCC'
}
_inv_currency_map = {v: k for k, v in _currency_map.items()}


class BittrexAPIAdapter(BitExRESTAdapter):
    _api_class = Bittrex

    @staticmethod
    def pair(base_currency: str, quote_currency: str) -> str:
        base_currency = _currency_map.get(base_currency, base_currency)
        quote_currency = _currency_map.get(quote_currency, quote_currency)
        return '{}-{}'.format(quote_currency, base_currency)

    @staticmethod
    def unpair(currency_pair: str) -> Tuple[str, str]:
        currencies = currency_pair.split('-')
        base_currency = _inv_currency_map.get(currencies[1], currencies[1])
        quote_currency = _inv_currency_map.get(currencies[0], currencies[0])
        return base_currency, quote_currency


class BittrexClient(BaseExchangeClient, PeriodicRefreshMixin):
    name = 'bittrex'
    _api_class = BittrexAPIAdapter

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        PeriodicRefreshMixin.__init__(self, refresh_interval=1)
