import logging
from typing import Dict, List, Tuple, Union

from coinbitrage import bitlogging
from coinbitrage.settings import DEFAULT_FEE, DEFAULT_QUOTE_CURRENCY
from coinbitrage.exchanges.interfaces import PublicMarketAPI, PrivateExchangeAPI


log = bitlogging.getLogger(__name__)


class BaseExchangeAPI(object):

    def __init__(self, name: str):
        self.name = name

    @staticmethod
    def pair(base_currency: str, quote_currency: str) -> str:
        return base_currency.upper() + quote_currency.upper()

    @staticmethod
    def unpair(currency_pair: str) -> Tuple[str, str]:
        base, quote = currency_pair[:len(currency_pair)/2], currency_pair[len(currency_pair)/2:]
        return base.upper(), quote.upper()

    def fee(self,
            base_currency: str,
            quote_currency: str = DEFAULT_QUOTE_CURRENCY) -> float:
        return DEFAULT_FEE

    def get_funds_from(self, from_exchange: PrivateExchangeAPI, currency: str, amount: float) -> bool:
        address = self.deposit_address(currency)
        result = from_exchange.withdraw(currency, address, amount)

        event_data = {'amount': amount, 'currency': currency, 'from_exchange': from_exchange.name,
                      'to_exchange': self.name, 'address': address}
        if result:
            log.info('Transfered {amount} {currency} from {from_exchange} to {to_exchange}',
                     event_name='exchange_api.transfer.success', event_data=event_data)
        else:
            log.warning('Unable to transfer {amount} {currency} from {from_exchange} to {to_exchange}',
                        event_name='exchange_api.transfer.failure', event_data=event_data)

        return result

class BaseExchangeClient(object):
    name = None
    _api_class = None

    def __init__(self, key_file: str, **kwargs):
        self.api = self._api_class(self.name, key_file, **kwargs)

    def __getattr__(self, name):
        return getattr(self.api, name)
