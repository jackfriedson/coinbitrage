from collections import defaultdict
from typing import Dict, Optional

from bitex import Kraken
from requests.exceptions import Timeout

from coinbitrage import bitlogging
from coinbitrage.exchanges.bitex import BitExAPIAdapter
from coinbitrage.exchanges.errors import ClientError, ExchangeError, ServerError
from coinbitrage.exchanges.mixins import ProxyCurrencyWrapper
from coinbitrage.settings import ACCEPTABLE_USDT_ASK, ACCEPTABLE_USDT_BID
from coinbitrage.utils import retry_on_exception

from .formatter import KrakenFormatter


log = bitlogging.getLogger(__name__)


KRAKEN_TIMEOUT = 30


class KrakenAPIAdapter(BitExAPIAdapter):
    _api_class = Kraken
    _deposit_methods = {
        'BTC': 'Bitcoin',
        'ETH': 'Ether (Hex)',
        'LTC': 'Litecoin',
        'USDT': 'Tether USD'
    }
    _error_cls_map = defaultdict(lambda: ClientError)
    _error_cls_map.update({
        'Service': ServerError,
    })
    formatter = KrakenFormatter()

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('timeout', KRAKEN_TIMEOUT)
        super(KrakenAPIAdapter, self).__init__(*args, **kwargs)

    def deposit_address(self, currency: str) -> str:
        deposit_method = self._deposit_methods.get(currency)
        if not deposit_method:
            raise NotImplementedError('Deposit address not implemented for {}'.format(currency))

        currency = self.formatter.format(currency)
        return super(KrakenAPIAdapter, self).deposit_address(currency, method=deposit_method)

    def raise_for_exchange_error(self, response_data: dict):
        errors = response_data.get('error')
        for error in errors:
            error_data = error.split(':')
            error_info, error_msg, error_extra = error_data[0], error_data[1], error_data[2:]
            severity, category = error_info[:1], error_info[1:]
            if severity == 'W':
                log.warning('Kraken API returned a warning -- {}'.format(error),
                            event_data={'category': category, 'message': error_msg, 'extra': error_extra},
                            event_name='kraken_api.warning')
            elif severity == 'E':
                log.warning('Kraken API returned an error -- {}'.format(error),
                            event_data={'category': category, 'message': error_msg, 'extra': error_extra},
                            event_name='kraken_api.error')
                error_cls = self._error_cls_map[category]
                raise error_cls(error_msg)

    @retry_on_exception(ServerError, Timeout)
    def order(self, order_id: str) -> Optional[dict]:
        order = self._wrapped_bitex_method('closed_orders')().get(order_id)
        if order is None:
            order = self._wrapped_bitex_method('orders')().get(order_id)
        return order


class KrakenTetherAdapter(ProxyCurrencyWrapper):

    def __init__(self, *args, **kwargs):
        api = KrakenAPIAdapter(*args, **kwargs)
        super(KrakenTetherAdapter, self).__init__(api,
                                                  proxy_currency='USDT',
                                                  quote_currency='USD',
                                                  acceptable_bid=ACCEPTABLE_USDT_BID,
                                                  acceptable_ask=ACCEPTABLE_USDT_ASK)
