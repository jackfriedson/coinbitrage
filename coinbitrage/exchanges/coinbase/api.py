from typing import Dict, Optional

from bitex import GDAX
from coinbase.wallet.client import Client

from coinbitrage import bitlogging, utils
from coinbitrage.exchanges.bitex import BitExAPIAdapter
from coinbitrage.exchanges.mixins import SeparateTradingAccountMixin

from .formatter import CoinbaseFormatter


log = bitlogging.getLogger(__name__)


class CoinbaseAPIAdapter(BitExAPIAdapter, SeparateTradingAccountMixin):
    _api_class = GDAX
    formatter = CoinbaseFormatter()

    def __init__(self, name: str, coinbase_key_file: str, gdax_key_file: str = None):
        super(CoinbaseAPIAdapter, self).__init__(name, gdax_key_file)
        coinbase_key, coinbase_secret = utils.load_key_from(coinbase_key_file)
        self._coinbase_client = Client(coinbase_key, coinbase_secret)
        self._account_ids = self._get_coinbase_accounts()

    def _get_coinbase_accounts(self):
        data = self._coinbase_client.get_accounts().data
        return {d['currency']: d['id'] for d in data}

    def deposit_address(self, currency: str) -> dict:
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

    # def limit_order(self, *args, fill_or_kill: bool = False, **kwargs) -> Optional[str]:
    #     # TODO: get fill or kill to work correctly
    #     return super(CoinbaseAPIAdapter, self).limit_order(*args, **kwargs)
