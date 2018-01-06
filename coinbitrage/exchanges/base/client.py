import functools

from coinbitrage import bitlogging
from coinbitrage.settings import Defaults


log = bitlogging.getLogger(__name__)


class BaseExchangeClient(object):
    name = None
    _api_class = None

    def __init__(self, key_file: str, **kwargs):
        self.api = self._api_class(self.name, key_file, **kwargs)
        self.supported_pairs = []
        self.currency_info = {}
        self.breaker_tripped = None

    def __getattr__(self, name):
        return getattr(self.api, name)

    def get_funds_from(self, from_exchange, currency: str, amount: float) -> bool:
        addr_info = self.api.deposit_address(currency)
        address = addr_info.pop('address')
        result = from_exchange.withdraw(currency, address, amount, **addr_info)

        event_data = {'amount': amount, 'currency': currency, 'from_exchange': from_exchange.name,
                      'to_exchange': self.name, 'address': address, 'address_info': addr_info}
        if result:
            log.info('Transfered {amount} {currency} from {from_exchange} to {to_exchange}',
                     event_name='exchange_api.transfer.success', event_data=event_data)
        else:
            log.warning('Unable to transfer {amount} {currency} from {from_exchange} to {to_exchange}',
                        event_name='exchange_api.transfer.failure', event_data=event_data)

        return result

    def trip_circuit_breaker(self, exc_types, call: functools.partial):
        log.warning('Circuit breaker tripped by {}', event_name='exchange_api.breaker_tripped',
                    event_data={'exchange': self.name, 'method': call.func.__name__,
                                'args': call.args, 'kwargs': call.keywords})
        self.breaker_tripped = {
            'time': time.time(),
            'retry': call,
            'exc_types': exc_types,
        }

    def supports_pair(self, base_currency: str, quote_currency: str) -> bool:
        pair = self.api.formatter.pair(base_currency, quote_currency)
        return pair in self.supported_pairs

    def tx_fee(self, currency: str) -> float:
        return float(self.currency_info[currency]['tx_fee'])

    def fee(self, base_currency: str, quote_currency: str) -> float:
        return Defaults.ORDER_FEE
