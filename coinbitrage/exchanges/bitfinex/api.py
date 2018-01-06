from bitex import Bitfinex

from coinbitrage import bitlogging
from coinbitrage.exchanges.bitex import BitExAPIAdapter
from coinbitrage.settings import Defaults
from coinbitrage.utils import retry_on_exception

from .formatter import BitfinexFormatter


log = bitlogging.getLogger(__name__)


class BitfinexAPIAdapter(BitExAPIAdapter):
    _api_class = Bitfinex
    formatter = BitfinexFormatter()

    def __init__(self, name: str, key_file: str):
        super(BitfinexAPIAdapter, self).__init__(name, key_file)
