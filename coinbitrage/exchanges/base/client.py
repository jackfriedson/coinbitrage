from coinbitrage import bitlogging


log = bitlogging.getLogger(__name__)


class BaseExchangeClient(object):
    name = None
    _api_class = None

    def __init__(self, key_file: str, **kwargs):
        self.api = self._api_class(self.name, key_file, **kwargs)
        self.supported_pairs = []
        self.currency_info = {}

    def __getattr__(self, name):
        return getattr(self.api, name)

    def bid(self):
        return self.bid_ask()['bid']

    def ask(self):
        return self.bid_ask()['ask']

    def get_funds_from(self, from_exchange, currency: str, amount: float) -> bool:
        address = self.api.deposit_address(currency)
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

    def supports_pair(self, base_currency: str, quote_currency: str) -> bool:
        pair = self.api.formatter.pair(base_currency, quote_currency)
        return pair in self.supported_pairs
