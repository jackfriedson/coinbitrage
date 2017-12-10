import logging
import time
from typing import Optional

from bitex import Poloniex

from coinbitrage import bitlogging
from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.bitex import BitExRESTAdapter
from coinbitrage.exchanges.mixins import PeriodicRefreshMixin
from coinbitrage.settings import DEFAULT_QUOTE_CURRENCY


class PoloniexAPIAdapter(BitExRESTAdapter):
    _api_class = Poloniex

    def __init__(self, name: str, key_file: str):
        super(PoloniexAPIAdapter, self).__init__(name, key_file)
        self._fee = None

    def fee(self,
            base_currency: str,
            quote_currency: str = DEFAULT_QUOTE_CURRENCY) -> float:
        if not self._fee:
            self._fee = float(self._api.fees().json()['takerFee'])
        return self._fee

    def deposit_address(self, currency: str) -> str:
        all_addresses = super(PoloniexAPIAdapter, self).deposit_address(currency)
        if currency in all_addresses:
            return all_addresses[currency]
        return self._generate_new_address(currency)

    def _generate_new_address(self, currency: str) -> str:
        params = {'currency': currency, 'command': 'generateNewAddress'}
        response = self._api.private_query('tradingApi', params=params)
        return response.json()['response']

    def limit_order(self, *args, fill_or_kill: bool = False, **kwargs) -> Optional[str]:
        if fill_or_kill:
            kwargs.update({'fill_or_kill': 1})
        return super(PoloniexAPIAdapter, self).limit_order(*args, **kwargs)

    @staticmethod
    def pair(base_currency: str, quote_currency: str) -> str:
        # Poloniex only has Tether exchanges, not USD
        if quote_currency == 'USD':
            quote_currency = 'USDT'

        return quote_currency + '_' + base_currency

    def unpair(currency_pair: str):
        currencies = currency_pair.split('_')
        return currencies[0], currencies[1]


class PoloniexClient(BaseExchangeClient, PeriodicRefreshMixin):
    name = 'poloniex'
    _api_class = PoloniexAPIAdapter

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        PeriodicRefreshMixin.__init__(self, 1)
