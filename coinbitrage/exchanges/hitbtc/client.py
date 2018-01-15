import time
from typing import Optional

from coinbitrage import bitlogging
from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.errors import ClientError
from coinbitrage.exchanges.mixins import WebsocketOrderBookMixin
from coinbitrage.settings import CURRENCIES
from coinbitrage.utils import retry_on_exception

from .api import HitBtcAPIAdapter
from .websocket import HitBtcWebsocketOrderBook


log = bitlogging.getLogger(__name__)


class HitBtcClient(BaseExchangeClient, WebsocketOrderBookMixin):
    _api_class = HitBtcAPIAdapter
    _websocket_order_book_class = HitBtcWebsocketOrderBook
    max_refresh_delay = 10
    name = 'hitbtc'

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        WebsocketOrderBookMixin.__init__(self)

    def init(self):
        pair_info = self.api.pairs()
        self.currency_info = self.api.currencies()
        self.supported_pairs = set(pair_info.keys())
        self._fees = {
            pair: float(info['takeLiquidityRate'])
            for pair, info in pair_info.items()
        }

    def tx_fee(self, currency: str) -> float:
        return CURRENCIES[currency]['hitbtc_withdraw_fee']

    def deposit_address(self, currency: str, **kwargs) -> Optional[dict]:
        if not self.currency_info[currency]['deposits_active']:
            return None

    def withdraw(self, currency: str, address: str, amount: float, **kwargs) -> bool:
        if not self.currency_info[currency]['withdrawals_active']:
            return False

        tx_info = self.api.withdraw(currency, address, amount, autoCommit=False, **kwargs)
        if not tx_info:
            return False

        tx_id = tx_info.get('id')

        @retry_on_exception(ClientError, max_retries=5, backoff_factor=1.)
        def wait_for_transaction(tx_id):
            return self.api.transaction(currency, txid=tx_id)

        tx_info = wait_for_transaction(tx_id)
        fees = float(tx_info['fee']) + float(tx_info['networkFee'])
        if fees > CURRENCIES[currency]['hitbtc_withdraw_fee']:
            log.warning('HitBTC withdrawal fee ({actual}) higher than expected ({expected}), skipping withdrawal',
                        event_name='hitbtc_api.unexpected_fee',
                        event_data={'exchange': self.name, 'currency': currency, 'actual': fees,
                                    'expected': CURRENCIES[currency]['hitbtc_withdraw_fee'], 'withdrawal_info': tx_info})
            self.api.rollback_withdrawal(tx_id)
            return False
        return self.api.commit_withdrawal(tx_id)
