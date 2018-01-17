from typing import Tuple

from coinbitrage import bitlogging
from coinbitrage.settings import CURRENCIES


log = bitlogging.getLogger(__name__)


class BaseFormatter(object):
    _currency_map = {}

    def __init__(self, pair_delimiter=''):
        self._pair_delimiter = pair_delimiter
        self._inverse_currency_map = {v: k for k, v in self._currency_map.items()}

    def __getattr__(self, name):
        return lambda x: x

    def format(self, currency: str, inverse: bool = False) -> str:
        currency = currency.upper()
        cur_map = self._currency_map if not inverse else self._inverse_currency_map
        return cur_map.get(currency, currency)

    def pair(self, base_currency: str, quote_currency: str) -> str:
        base = self.format(base_currency)
        quote = self.format(quote_currency)
        return f'{base}{self._pair_delimiter}{quote}'

    def unpair(self, currency_pair: str) -> Tuple[str, str]:
        if self._pair_delimiter:
            base, quote = tuple(currency_pair.split(self._pair_delimiter))
        else:
            mid = len(currency_pair) // 2
            base, quote = currency_pair[:mid], currency_pair[mid:]
            if len(currency_pair) % 2 != 0 and not (base in CURRENCIES and quote in CURRENCIES):
                base, quote = currency_pair[:mid+1], currency_pair[mid+1:]
        base = self.format(base, inverse=True)
        quote = self.format(quote, inverse=True)
        return base, quote
