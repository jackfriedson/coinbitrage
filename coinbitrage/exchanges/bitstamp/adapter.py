import json
import logging
from typing import Dict, List, Optional, Union

from bitex import Bitstamp
from bitex.api.WSS import BitstampWSS

from coinbitrage import bitlogging
from coinbitrage.exchanges.base import BaseExchangeClient
from coinbitrage.exchanges.bitex import BitExAPIAdapter, BitExWSSAdapter
from coinbitrage.exchanges.mixins import WebsocketMixin
from coinbitrage.settings import DEFAULT_QUOTE_CURRENCY


class BitstampAPIAdapter(BitExAPIAdapter):
    _api_class = Bitstamp

    def __init__(self, name: str, key_file: str):
        super(BitstampAPIAdapter, self).__init__(name, key_file)
        self._fees = None

    def fee(self,
            base_currency: str,
            quote_currency: str = DEFAULT_QUOTE_CURRENCY) -> float:
        if not self._fees:
            data = self._api.balance().json()
            self._fees = {
                k: float(v) / 100.
                for k, v in data.items()
                if k.endswith('_fee')
            }

        pair = self.pair(base_currency, quote_currency)
        fee = self._fees.get(pair + '_fee')

        if not fee:
            raise ValueError('{} is not a supported pair'.format(pair))
        return fee

    def limit_order(self, *args, **kwargs) -> Optional[str]:
        # Bitstamp doesn't support fill-or-kill limit orders :(
        kwargs.pop('fill_or_kill', None)
        return super(BitstampAPIAdapter, self).limit_order(*args, **kwargs)

    def pair(self, base_currency: str, quote_currency: str) -> str:
        return base_currency.lower() + quote_currency.lower()


class BitstampClient(BaseExchangeClient, WebsocketMixin):
    name = 'bitstamp'
    _api_class = BitstampAPIAdapter

    def __init__(self, key_file: str):
        BaseExchangeClient.__init__(self, key_file)
        WebsocketMixin.__init__(self, BitExWSSAdapter(BitstampWSS()))
        self._websocket._formatters.update({
            'order_book': lambda x: {
                'bid': float(max(x[2]['bids'], key=lambda y: float(y[0]))[0]),
                'ask': float(min(x[2]['asks'], key=lambda y: float(y[0]))[0]),
                'time': x[3],
            }
        })
        self._channels = set()

    def start_live_updates(self,
                           base_currency: str,
                           quote_currency: str = DEFAULT_QUOTE_CURRENCY):
        channel = 'order_book'
        pair = self.pair(base_currency, quote_currency)

        if pair != 'btcusd':
            channel += '_' + pair

        self._channels.add(channel)
        self._websocket._init_websocket(BitstampWSS(include_only=self._channels))
        self._websocket.subscribe(self.pair(base_currency, quote_currency), 'order_book')
