from bitex import Bitfinex

from coinbitrage import bitlogging
from coinbitrage.exchanges.bitex import BitExAPIAdapter
from coinbitrage.settings import CURRENCIES, Defaults
from coinbitrage.utils import retry_on_exception

from .formatter import BitfinexFormatter


log = bitlogging.getLogger(__name__)


class BitfinexAPIAdapter(BitExAPIAdapter):
    _api_class = Bitfinex
    formatter = BitfinexFormatter()

    def __init__(self, name: str, key_file: str):
        super(BitfinexAPIAdapter, self).__init__(name, key_file)

    def deposit_address(self, currency: str) -> dict:
        deposit_method = CURRENCIES[currency].get('bitfinex_method')
        if not deposit_method:
            raise NotImplementedError(f'Deposit address not implemented for {currency}')

        currency = self.formatter.format(currency)
        result = super(BitfinexAPIAdapter, self).deposit_address(currency, method=deposit_method,
                                                                 wallet_name='exchange')

        if currency.upper() == 'XRP':
            result['paymentId'] = result.pop('address')
            result['address'] = result.pop('address_pool')

        return result

    def withdraw(self, currency: str, address: str, amount: float, **kwargs) -> bool:
        withdraw_method = CURRENCIES[currency].get('bitfinex_method')
        if not withdraw_method:
            raise NotImplementedError(f'Withdraw not implemented for {currency}')

        kwargs.update({'withdraw_type': withdraw_method, 'walletselected': 'exchange'})
        if 'paymentId' in kwargs:
            kwargs['payment_id'] = kwargs.pop('paymentId')

        return super(BitfinexAPIAdapter, self).withdraw(currency, address, amount, **kwargs)
