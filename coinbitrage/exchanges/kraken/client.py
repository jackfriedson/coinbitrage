from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.mixins import PeriodicRefreshMixin

from .api import KrakenTetherAdapter


KRAKEN_CALL_RATE = 3


class KrakenClient(BaseExchangeClient, PeriodicRefreshMixin):
    name = 'kraken'
    _api_class = KrakenTetherAdapter

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        PeriodicRefreshMixin.__init__(self, refresh_interval=KRAKEN_CALL_RATE)

    def init(self):
        self.supported_pairs = self.api.pairs()

    def supports_pair(self, base_currency: str, quote_currency: str) -> bool:
        if isinstance(self.api, KrakenTetherAdapter) and quote_currency == 'USDT':
            quote_currency = 'USD'

        return super(KrakenClient, self).supports_pair(base_currency, quote_currency)
