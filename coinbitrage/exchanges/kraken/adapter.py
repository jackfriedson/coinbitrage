import time
from typing import Dict, List, Optional, Union

from bitex import Kraken

from coinbitrage import bitlogging, settings
from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.bitex import BitExRESTAdapter
from coinbitrage.exchanges.errors import ClientError, ExchangeError, ServerError
from coinbitrage.exchanges.mixins import PeriodicRefreshMixin


log = bitlogging.getLogger(__name__)


KRAKEN_TIMEOUT = 20
KRAKEN_API_CALL_RATE = 3.
ACCEPTABLE_USDT_ASK = 1.01
ACCEPTABLE_USDT_BID = 0.99


class KrakenAPIAdapter(BitExRESTAdapter):
    _api_class = Kraken
    _currency_map = {
        'BTC': 'XXBT',
        'ETH': 'XETH',
        'USD': 'ZUSD',
    }
    _error_cls_map = {
        'General': ClientError,
        'Service': ServerError,
        'Trade': ClientError,
        'Order': ClientError,
    }

    def __init__(self, *args, **kwargs):
        if 'timeout' not in kwargs:
            kwargs['timeout'] = KRAKEN_TIMEOUT
        super(KrakenAPIAdapter, self).__init__(*args, **kwargs)

    def deposit_address(self, currency: str) -> str:
        if currency == 'BTC':
            method = 'Bitcoin'
        elif currency == 'ETH':
            method = 'Ether (Hex)'
        elif currency == 'USDT':
            method = 'Tether USD'
        else:
            raise NotImplementedError('Deposit address not implemented for {}'.format(currency))

        currency = self.fmt_currency(currency)
        resp = self._api.deposit_address(asset=currency, method=method)
        resp.raise_for_status()
        resp_data = resp.json()
        self.raise_for_exchange_error(resp_data)
        addr = resp_data['result'][0]['address']
        return addr

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


class KrakenTetherAdapter(KrakenAPIAdapter):

    def balance(self):
        balances = super(KrakenTetherAdapter, self).balance()
        usdt_bal = balances.get('USDT', 0.)

        if usdt_bal == 0.:
            balances['USDT'] = balances.pop('USD', 0.)
            return balances

        if not self._usdt_to_usd(usdt_bal):
            raise ExchangeError('Couldn\'t sell USDT')

        balances = super(KrakenTetherAdapter, self).balance()
        assert balances.get('USDT', 0.) == 0.
        balances['USDT'] = balances.pop('USD', 0.)
        return balances

    def withdraw(self, currency: str, address: str, amount: float, **kwargs) -> str:
        if currency != 'USDT':
            return super(KrakenTetherAdapter, self).withdraw(currency, address, amount, **kwargs)

        if not self._usd_to_usdt(amount):
            raise ExchangeError('Couldn\'t buy USDT')

        return super(KrakenTetherAdapter, self).withdraw(currency, address, amount, **kwargs)

    def limit_order(self,
                    base_currency: str,
                    *args,
                    quote_currency: str = settings.DEFAULT_QUOTE_CURRENCY,
                    **kwargs) -> Optional[str]:
        if base_currency == 'USDT':
            base_currency = 'USD'
        if quote_currency == 'USDT':
            quote_currency = 'USD'
        return super(KrakenTetherAdapter, self).limit_order(base_currency, *args, quote_currency=quote_currency, **kwargs)

    def _usdt_to_usd(self, amount: float):
        usdt_bid = self.ticker(self.pair('USDT', 'USD'))['bid']
        if usdt_bid < ACCEPTABLE_USDT_BID:
            error_msg = 'Kraken USDT/USD bid is {} which is lower than the acceptable bid of {}'
            raise ExchangeError(error_msg.format(usdt_bid, ACCEPTABLE_USDT_BID))

        price = usdt_bid * (1 - settings.ORDER_PRECISION)
        usdt_sell = super(KrakenTetherAdapter, self).limit_order('USDT', 'sell', price, amount, quote_currency='USD')
        return usdt_sell

    def _usd_to_usdt(self, amount: float):
        usdt_ask = self.ticker(self.pair('USDT', 'USD'))['ask']
        if usdt_ask > ACCEPTABLE_USDT_ASK:
            error_msg = 'Kraken USDT/USD ask is {} which is higher than the acceptable ask of {}'
            raise ExchangeError(error_msg.format(usdt_ask, ACCEPTABLE_USDT_ASK))

        price = usdt_ask * (1 + settings.ORDER_PRECISION)
        usdt_buy = super(KrakenTetherAdapter, self).limit_order('USDT', 'buy', price, amount, quote_currency='USD')
        return usdt_buy


class KrakenClient(BaseExchangeClient, PeriodicRefreshMixin):
    name = 'kraken'
    _api_class = KrakenTetherAdapter

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        PeriodicRefreshMixin.__init__(self, refresh_interval=1)

