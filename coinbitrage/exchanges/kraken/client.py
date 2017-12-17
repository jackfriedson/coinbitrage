from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.mixins import PeriodicRefreshMixin

from .api import KrakenTetherAdapter


KRAKEN_CALL_RATE = 3


class KrakenClient(BaseExchangeClient, PeriodicRefreshMixin):
    name = 'kraken'
    _api_class = KrakenTetherAdapter
    _tx_fees = {
        'BCH': 0.001,
        'BTC': 0.001,
        'ETH': 0.005,
        'LTC': 0.001,
        'USDT': 5.,
    }

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        PeriodicRefreshMixin.__init__(self, refresh_interval=KRAKEN_CALL_RATE)

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
        return self._tx_fees[currency]

    def fee(self, base_currency: str, quote_currency: str) -> float:
        if isinstance(self.api, KrakenTetherAdapter) and quote_currency == 'USDT':
            quote_currency = 'USD'
        pair = self.api.formatter.pair(base_currency, quote_currency)
        return self._fees[pair]
