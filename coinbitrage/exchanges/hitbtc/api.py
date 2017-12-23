from typing import Dict

from bitex import HitBtc
from requests.exceptions import Timeout

from coinbitrage import bitlogging
from coinbitrage.exchanges.bitex import BitExAPIAdapter
from coinbitrage.exchanges.errors import ClientError, ServerError
from coinbitrage.exchanges.mixins import SeparateTradingAccountMixin
from coinbitrage.settings import DEFAULT_QUOTE_CURRENCY
from coinbitrage.utils import retry_on_exception

from .formatter import HitBtcFormatter


log = bitlogging.getLogger(__name__)


class HitBtcAPIAdapter(BitExAPIAdapter, SeparateTradingAccountMixin):
    _api_class = HitBtc
    formatter = HitBtcFormatter()

    @retry_on_exception(Timeout, ServerError)
    def bank_balance(self) -> Dict[str, float]:
        resp = self._api.private_query('account/balance', method_verb='GET')
        resp.raise_for_status()
        return {
            self.formatter.format(val['currency'], inverse=True): float(val['available'])
            for val in resp.json()
        }

    @retry_on_exception(Timeout, ServerError)
    def _transfer_between_accounts(self, to_trading: bool, currency: str, amount: float):
        direction = 'bankToExchange' if to_trading else 'exchangeToBank'
        params = {'currency': self.formatter.format(currency), 'amount': amount, 'type': direction}
        resp = self._api.private_query('account/transfer', method_verb='POST', params=params)
        return 'id' in resp.json()

    def raise_for_exchange_error(self, response_data: dict):
        if isinstance(response_data, dict) and 'error' in response_data:
            error = response_data.get('error')
            log.warning('HitBTC API returned an error -- {message}', event_name='hitbtc_api.warning',
                        event_data=error)
            error_cls = ServerError if int(error['code']) in [500, 503, 504] else ClientError
            raise error_cls(error['message'])

    def withdraw(self, currency: str, address: str, amount: float, **kwargs) -> bool:
        if self.trading_to_bank(currency, amount):
            return super(HitBtcAPIAdapter, self).withdraw(currency, address, amount)