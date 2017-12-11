from typing import Tuple

from bitex import Bittrex

from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.bitex import BitExRESTAdapter
from coinbitrage.exchanges.mixins import PeriodicRefreshMixin


class BittrexAPIAdapter(BitExRESTAdapter):
    _api_class = Bittrex

    def __init__(self, name: str, key_file: str):
        super(BittrexAPIAdapter, self).__init__(name, key_file)

    @staticmethod
    def pair(base_currency: str, quote_currency: str) -> str:
        return '{}-{}'.format(quote_currency, base_currency)

    @staticmethod
    def unpair(currency_pair: str) -> Tuple[str, str]:
        currencies = currency_pair.split('-')
        return currencies[1], currencies[0]


class BittrexClient(BaseExchangeClient, PeriodicRefreshMixin):
    name = 'bittrex'
    _api_class = BittrexAPIAdapter

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        PeriodicRefreshMixin.__init__(self, refresh_interval=1)
