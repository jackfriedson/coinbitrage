import time

from coinbitrage import bitlogging
from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.mixins import PeriodicRefreshMixin

from .api import HitBtcAPIAdapter


log = bitlogging.getLogger(__name__)


class HitBtcClient(BaseExchangeClient, PeriodicRefreshMixin):
    name = 'hitbtc'
    _api_class = HitBtcAPIAdapter
    _tx_fees = {
        'BCH': 0.002,
        'BTC': 0.001,
        'ETH': 0.01,
        'LTC': 0.003,
        'USDT': 100.,
    }

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        PeriodicRefreshMixin.__init__(self, 1)

    def init(self):
        pair_info = self.api.pairs()
        self.currency_info = self.api.currencies()
        self.supported_pairs = set(pair_info.keys())
        self._fees = {
            pair: float(info['takeLiquidityRate'])
            for pair, info in pair_info.items()
        }

    def tx_fee(self, currency: str) -> float:
        return self._tx_fees[currency]

    def withdraw(self, currency: str, address: str, amount: float, **kwargs) -> bool:
        tx_id = self.api.withdraw(currency, address, amount, autoCommit=False)
        time.sleep(0.5)
        tx_info = self.api.transaction(currency, txid=tx_id)
        fees = tx_info['fee'] + tx_info['networkFee']
        if fees > self._tx_fees[currency]:
            log.warning('HitBTC withdrawal fee ({actual}) higher than expected ({expected})',
                        event_name='hitbtc_api.unexpected_fee',
                        event_data={'exchange': self.name, 'currency': currency, 'actual': fees,
                                    'expected': self._tx_fees[currency], 'withdrawal_info': tx_info})
            self.api.rollback_withdrawal(tx_id)
            raise ExchangeError('Withdrawal fee higher than expected')
        return self.api.commit_withdrawal(tx_id)
