from typing import Optional, Tuple

from bitex import Bittrex

from coinbitrage import bitlogging
from coinbitrage.exchanges.bitex import BitExAPIAdapter
from coinbitrage.exchanges.errors import ClientError

from .formatter import BittrexFormatter


log = bitlogging.getLogger(__name__)


BITTREX_TIMEOUT = 15


class BittrexAPIAdapter(BitExAPIAdapter):
    _api_class = Bittrex
    formatter = BittrexFormatter()
    ripple_address = 'rPVMhWBsfF9iMXYj3aAzJVkPDTFNSyWdKy'

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('timeout', BITTREX_TIMEOUT)
        super(BittrexAPIAdapter, self).__init__(*args, **kwargs)

    def raise_for_exchange_error(self, response_data: dict):
        if not response_data.get('success', False):
            error_msg = response_data.get('message')
            log.warning('Bittrex API returned an error -- {message}',
                        event_name='bittrex_api.error',
                        event_data={'exchange': self.name, 'message': error_msg})
            raise ClientError(error_msg)

    def deposit_address(self, currency: str) -> dict:
        addr_info = super(BittrexAPIAdapter, self).deposit_address(currency)
        if currency == 'XRP':
            addr_info = {
                'address': self.ripple_address,
                'paymentId': addr_info['address']
            }
        return addr_info

    def withdraw(self, *args, **kwargs) -> bool:
        if 'tag' in kwargs:
            kwargs.update({'paymentId': kwargs.pop('tag')})
        return super(BittrexAPIAdapter, self).withdraw(*args, **kwargs)
