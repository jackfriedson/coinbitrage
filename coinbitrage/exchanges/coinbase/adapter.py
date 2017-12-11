import logging
from typing import Dict, List, Optional, Union

from bitex import GDAX
from coinbase.wallet.client import Client

from coinbitrage import bitlogging
from coinbitrage.exchanges import utils
from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.bitex import BitExRESTAdapter
from coinbitrage.exchanges.interfaces import PrivateExchangeAPI
from coinbitrage.exchanges.mixins import SeparateTradingAccountMixin, WebsocketMixin
from coinbitrage.settings import DEFAULT_QUOTE_CURRENCY

from .websocket import CoinbaseWebsocket

log = bitlogging.getLogger(__name__)


class CoinbaseAPIAdapter(BitExRESTAdapter, SeparateTradingAccountMixin):
    _api_class = GDAX
    _fees = {
        'BTC': 0.0025,
        'ETH': 0.003,
        'LTC': 0.003
    }

    def __init__(self, name: str, coinbase_key_file: str, gdax_key_file: str = None):
        super(CoinbaseAPIAdapter, self).__init__(name, gdax_key_file)
        coinbase_key, coinbase_secret = utils.load_key_from(coinbase_key_file)
        self._coinbase_client = Client(coinbase_key, coinbase_secret)
        self._account_ids = self._get_coinbase_accounts()

    def fee(self,
            base_currency: str,
            quote_currency: str = DEFAULT_QUOTE_CURRENCY) -> float:
        return self._fees[base_currency]

    def _get_coinbase_accounts(self):
        data = self._coinbase_client.get_accounts().data
        return {d['currency']: d['id'] for d in data}

    def deposit_address(self, currency: str) -> str:
        account_id = self._account_ids[currency]
        new_address = self._coinbase_client.create_address(account_id).address
        return new_address

    def _transfer_between_accounts(self, to_trading: bool, currency: str, amount: float):
        endpoint = 'deposits' if to_trading else 'withdrawals'
        params = {
            'amount': str(amount),
            'currency': currency,
            'coinbase_account_id': self._account_ids[currency]
        }
        resp = self._api.private_query('{}/coinbase-account'.format(endpoint), params=params)
        return 'id' in resp.json()

    def bank_balance(self) -> Dict[str, float]:
        resp = self._coinbase_client.get_accounts()
        return {
            acct['balance']['currency']: float(acct['balance']['amount'])
            for acct in resp.data
        }

    def limit_order(self, *args, fill_or_kill: bool = False, **kwargs) -> Optional[str]:
        # TODO: get fill or kill to work correctly
        return super(CoinbaseAPIAdapter, self).limit_order(*args, **kwargs)

    def pair(self, base_currency: str, quote_currency: str) -> str:
        return base_currency + '-' + quote_currency

    def unpair(self, currency_pair: str) -> str:
        currencies = currency_pair.split('-')
        return currencies[0], currencies[1]


class CoinbaseClient(BaseExchangeClient, WebsocketMixin):
    name = 'coinbase'
    _api_class = CoinbaseAPIAdapter

    def __init__(self, coinbase_key_file: str, gdax_key_file: str = None):
        BaseExchangeClient.__init__(self, coinbase_key_file, gdax_key_file=gdax_key_file)
        WebsocketMixin.__init__(self, CoinbaseWebsocket())
