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
