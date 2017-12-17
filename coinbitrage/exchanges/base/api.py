from typing import Optional, Tuple

from coinbitrage.settings import DEFAULT_ORDER_FEE, DEFAULT_QUOTE_CURRENCY

from .formatter import BaseFormatter


class BaseExchangeAPI(object):
    """An exchange's REST API. Handles making requests, formatting responses, parsing errors
    and raising them.
    """
    formatter = BaseFormatter()

    def __init__(self, name: str):
        self.name = name

    def fee(self,
            base_currency: str,
            quote_currency: str = DEFAULT_QUOTE_CURRENCY) -> float:
        return DEFAULT_ORDER_FEE

    def deposit_address(self, currency: str) -> str:
        raise NotImplementedError

    def balance(self):
        raise NotImplementedError

    def withdraw(self, currency: str, address: str, amount: float, **kwargs) -> bool:
        raise NotImplementedError

    def limit_order(self,
                    base_currency: str,
                    side: str,
                    price: float,
                    volume: float,
                    quote_currency: str = DEFAULT_QUOTE_CURRENCY,
                    **kwargs) -> Optional[str]:
        raise NotImplementedError

    def wait_for_fill(self, order_id: str, sleep: int = 1, timeout: int = 60):
        raise NotImplementedError
