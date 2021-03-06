from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.mixins import RefreshOrderBookMixin
from coinbitrage.settings import CURRENCIES

from .api import KrakenAPIAdapter, KrakenTetherAdapter


KRAKEN_CALL_RATE = 2


class KrakenClient(BaseExchangeClient, RefreshOrderBookMixin):
    _api_class = KrakenAPIAdapter
    name = 'kraken'

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        RefreshOrderBookMixin.__init__(self, refresh_interval=KRAKEN_CALL_RATE)

    def init(self):
        pair_info = self.api.pairs()
        self.supported_pairs = set(pair_info.keys())
        self._fees = {
            pair: info['fees'][0][1] / 100
            for pair, info in pair_info.items()
        }

    def supports_pair(self, base_currency: str, quote_currency: str) -> bool:
        if isinstance(self.api, KrakenTetherAdapter) and quote_currency == 'USDT':
            quote_currency = 'USD'
        return super(KrakenClient, self).supports_pair(base_currency, quote_currency)

    def tx_fee(self, currency: str) -> float:
        return CURRENCIES[currency]['kraken_withdraw_fee']

    def fee(self, base_currency: str, quote_currency: str) -> float:
        result = 0
        if isinstance(self.api, KrakenTetherAdapter) and quote_currency == 'USDT':
            quote_currency = 'USD'
            proxy_pair = self.api.formatter.pair(self.api.proxy_currency, self.api.quote_currency)
            result += self._fees[proxy_pair]
        pair = self.api.formatter.pair(base_currency, quote_currency)
        return result + self._fees[pair]
