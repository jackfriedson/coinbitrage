from typing import Tuple


class BaseFormatter(object):
    _currency_map = {}

    def __init__(self, pair_delimiter=''):
        self._pair_delimiter = pair_delimiter
        self._inverse_currency_map = {v: k for k, v in self._currency_map.items()}

    def __getattr__(self, name):
        return lambda x: x

    def format(self, currency: str, inverse: bool = False) -> str:
        currence = currency.upper()
        cur_map = self._currency_map if not inverse else self._inverse_currency_map
        return cur_map.get(currency, currency)

    def pair(self, base_currency: str, quote_currency: str) -> str:
        base = self.format(base_currency)
        quote = self.format(quote_currency)
        return '{}{}{}'.format(base, self._pair_delimiter, quote)

    def unpair(self, currency_pair: str) -> Tuple[str, str]:
        if self._pair_delimiter:
            base, quote = tuple(currency_pair.split(self._pair_delimiter))
        else:
            mid = len(currency_pair)/2
            base, quote = currency_pair[:mid], currency_pair[mid:]
        base = self.format(base, inverse=True)
        quote = self.format(quote, inverse=True)
        return base, quote
