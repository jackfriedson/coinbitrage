"""
Implements core Kraken API funcitonality
"""

import base64
import hashlib
import hmac
import time
import urllib.parse

import requests

from coinbitrage.exchanges.exceptions import APIException, AuthorizationException, ServiceUnavailableException
from coinbitrage.exchanges.utils import retry_on_exception, retry_on_status_code


base_url = 'https://api.kraken.com'
api_version = '0'
max_call_count = 15
decrement_freq = 3


class KrakenAPI(object):

    def __init__(self, key=None, secret=None):
        self.key = key
        self.secret = secret
        self._call_counter = 0
        self._last_decrement = None

    def load_api_key(self, path):
        with open(path, 'r') as f:
            self.key = f.readline().strip()
            self.secret = f.readline().strip()

    def _increment_call_count(self, value=1):
        if self._last_decrement is None:
            self._last_decrement = time.time()
        self._call_counter += value

    @property
    def call_count(self):
        """ Computes an estimate of the current call count.

        Note: This may differ from the actual call count due to both time skew and differences
        in call count computation between client and server.
        """
        if self._last_decrement is not None:
            current_time = time.time()
            elapsed = current_time - self._last_decrement
            decrement_by = int(elapsed) / decrement_freq
            if decrement_by > self._call_counter:
                self._call_counter = 0
                self._last_decrement = None
            else:
                self._call_counter -= decrement_by
                self._last_decrement = current_time - (elapsed - (decrement_by * decrement_freq))

        return self._call_counter

    @retry_on_status_code([500, 502, 503, 504])
    def _call(self, method, url, headers=None, params=None, data=None):
        headers = headers or {}
        params = params or {}
        data = data or {}

        call_count_difference = self.call_count - max_call_count
        if call_count_difference > 0:
            time.sleep((call_count_difference + 1) * decrement_freq)

        return requests.request(method, url, headers=headers, params=params, data=data)

    @retry_on_exception(ServiceUnavailableException)
    def _call_and_raise(self, *args, **kwargs):
        resp = self._call(*args, **kwargs)
        resp.raise_for_status()
        errors = resp.json().get('error')
        if errors:
            for error in errors:
                if error == 'EService:Unavailable':
                    raise ServiceUnavailableException()
            raise APIException(str(errors))
        return resp.json().get('result')

    def _call_public(self, endpoint, params=None):
        url = base_url + '/' + api_version + '/public/' + endpoint
        return self._call_and_raise('GET', url, params=params)

    def _call_private(self, endpoint, data=None, inc_call_count=1):
        """ Send a POST request to one of Kraken's private endpoints.

        Requires a valid API Key and API secret to be set.

        :param endpoint: Kraken endpoint to POST to
        :type endpoint: str
        :param data: request data
        :type data: dict
        :param inc_call_count: value to increment the current call count by
        :type inc_call_count: int
        """
        uri = '/' + api_version + '/private/' + endpoint
        url = base_url + uri

        if data is None:
            data = {}

        if self.key is None or self.secret is None:
            raise AuthorizationException('Must provide a valid API Key and API Secret')

        data['nonce'] = int(1000 * time.time())
        postdata = urllib.parse.urlencode(data)
        encoded = (str(data['nonce']) + postdata).encode()
        message = uri.encode() + hashlib.sha256(encoded).digest()
        signature = hmac.new(base64.b64decode(self.secret), message, hashlib.sha512)
        sigdigest = base64.b64encode(signature.digest())

        headers = {
            'API-Key': self.key,
            'API-Sign': sigdigest.decode()
        }

        resp = self._call_and_raise('POST', url, data=data, headers=headers)

        if inc_call_count:
            self._increment_call_count(value=inc_call_count)

        return resp

    @classmethod
    def _create_dict_from_args(cls, **kwargs):
        return {k: v for k, v in kwargs.items() if v is not None}

    #####################################################
    #                   Public Methods                  #
    #####################################################
    def get_server_time(self):
        return self._call_public('Time')

    def get_asset_info(self, info=None, aclass=None, asset=None):
        """
        :param info: info to retrieve
        :param aclass: asset class
        :param asset: comma delimited list of assets to get info on
        """
        params = self._create_dict_from_args(info=info, aclass=aclass, asset=asset)
        return self._call_public('Assets', params=params)

    def get_tradable_asset_pairs(self, info=None, pair=None):
        """
        :param info: info to retrieve:
                     'info' = all info (default)
                     'leverage' = leverage info
                     'fees' = fees schedule
                     'margin' = margin info
        :param pair: comma delimited list of asset pairs to get info on
        """
        params = self._create_dict_from_args(info=info, pair=pair)
        return self._call_public('AssetPairs', params=params)

    def get_ticker_info(self, pair):
        """
        :param pair: comma delimited list of asset pairs to get info on
        """
        params = self._create_dict_from_args(pair=pair)
        return self._call_public('Ticker', params=params)

    def get_OHLC_data(self, pair, interval=None, since=None):
        """
        :param pair: asset pair to get OHLC data for
        :param interval: time frame interval in minutes:
                         1 (default), 5, 15, 30, 60, 240, 1440, 10080, 21600
        :param since: return committed OHLC data since given id (exclusive)
        """
        params = self._create_dict_from_args(pair=pair, interval=interval, since=since)
        return self._call_public('OHLC', params=params)

    def get_order_book(self, pair, count=None):
        """
        :param pair: asset pair to get market depth for
        :param count: maximum number of asks/bids
        """
        params = self._create_dict_from_args(pair=pair, count=count)
        return self._call_public('Depth', params=params)

    def get_recent_trades(self, pair, since=None):
        """
        :param pair: asset pair to get trade data for
        :param since: return trade data since given id (exclusive)
        """
        params = self._create_dict_from_args(pair=pair, since=since)
        return self._call_public('Trades', params=params)

    def get_recent_spread_data(self, pair, since=None):
        """
        :param pair: aasset pair to get spread data for
        :param since: return spread data since given id (inclusive)
        """
        params = self._create_dict_from_args(pair=pair, since=since)
        return self._call_public('Spread', params=params)

    #####################################################
    #                  Private Methods                  #
    #####################################################
    def get_account_balance(self):
        return self._call_private('Balance')

    def get_trade_balance(self, aclass=None, asset=None):
        """
        :param aclass: asset class (default = currency)
        :param asset: base asset used to determine balance (default = ZUSD)
        """
        data = self._create_dict_from_args(aclass=aclass, asset=asset)
        return self._call_private('TradeBalance', data=data)

    def get_open_orders(self, trades=False, userref=None):
        """
        :param trades: whether or not to include trades in output (default = false)
        :param userref: restrict results to given user reference id
        """
        data = self._create_dict_from_args(trades=str(trades).lower(), userref=userref)
        return self._call_private('OpenOrders', data=data)

    def get_closed_orders(self, trades=False, userref=None, start=None, end=None, closetime=None, ofs=None):
        """
        :param trades: whether or not to include trades in output
        :param userref: restrict results to given user reference id
        :param start: starting unix timestamp or order tx id of results (exclusive)
        :param end: ending unix timestamp or order tx id of results (inclusive)
        :param ofs: result offset
        :param closetime: which time to use:
                          open
                          close
                          both (default)
        """
        data = self._create_dict_from_args(trades=str(trades).lower(), userref=userref,
                                           start=start, end=end, closetime=closetime, ofs=ofs)
        return self._call_private('ClosedOrders', data=data)

    def query_orders_info(self, txid, trades=False, userref=None):
        """
        :param txid: comma delimited list of transaction ids to query info about (20 maximum)
        :param trades: whether or not to include trades in output (default = false)
        :param userref: restrict results to given user reference id
        """
        data = self._create_dict_from_args(txid=txid, trades=str(trades).lower(), userref=userref)
        return self._call_private('QueryOrders', data=data)

    def get_trades_history(self, type=None, trades=False, start=None, end=None, ofs=None):
        """
        :param type: type of trade:
                     all = all types (default)
                     any position = any position (open or closed)
                     closed position = positions that have been closed
                     closing position = any trade closing all or part of a position
        :param trades: whether or not to include trades related to position in output (default = false)
        :param start: starting unix timestamp or trade tx id of results
        :param end: ending unix timestamp or trade tx id of results
        :param ofs: result offset
        """
        data = self._create_dict_from_args(type=type, trades=str(trades).lower(), start=start, end=end,
                                           ofs=ofs)
        return self._call_private('TradesHistory', data=data, inc_call_count=2)

    def query_trades_info(self, txid, trades=False):
        """
        :param txid: comma delimited list of transaction ids to query info about (20 maximum)
        :param trades: whether or not to include trades related to position in output
        """
        data = self._create_dict_from_args(txid=txid, trades=str(trades).lower())
        return self._call_private('QueryTrades', data=data, inc_call_count=2)

    def get_open_positions(self, txid, docalcs=False):
        """
        :param txid: comma delimited list of transaction ids to restrict output to
        :param docalcs: whether or not to include profit/loss calculations (default = false)
        """
        data = self._create_dict_from_args(txid=txid, docalcs=docalcs)
        return self._call_private('OpenPositions', data=data)

    def get_ledgers_info(self, aclass=None, asset=None, type=None, start=None, end=None, ofs=None):
        """
        :param aclass: asset class (default = currency)
        :param asset: comma delimited list of assets to restrict output to (default = all)
        :param type: type of ledger to retrieve:
                     all (default)
                     deposit
                     withdrawal
                     trade
                     margin
        :param start: starting unix timestamp or ledger id of results (exclusive)
        :param end: ending unix timestamp or ledger id of results (inclusive)
        :param ofs: result offset
        """
        data = self._create_dict_from_args(aclass=aclass, asset=asset, type=type, start=start,
                                           end=end, ofs=ofs)
        return self._call_private('Ledgers', data=data, inc_call_count=2)

    def query_ledgers(self, id):
        """
        :param id: comma delimited list of ledger ids to query info about (20 maximum)
        """
        data = self._create_dict_from_args(id=id)
        return self._call_private('QueryLedgers', data=data, inc_call_count=2)

    def get_trade_volume(self, pair=None, fee_info=False):
        """
        :param pair: comma delimited list of asset pairs to get fee info on
        :param fee_info: whether or not to include fee info in results
        """
        data = self._create_dict_from_args(pair=pair)
        data['fee-info'] = str(fee_info).lower()
        return self._call_private('TradeVolume', data=data)

    def add_standard_order(self, pair, type, ordertype, volume, price=None, price2=None,
                           leverage=None, oflags=None, starttm=None, expiretm=None, userref=None,
                           validate=None, close=None):
        """
        :param pair: asset pair
        :param type: type of order (buy/sell)
        :param ordertype: order type:
                        market
                        limit (price = limit price)
                        stop-loss (price = stop loss price)
                        take-profit (price = take profit price)
                        stop-loss-profit (price = stop loss price, price2 = take profit price)
                        stop-loss-profit-limit (price = stop loss price, price2 = take profit price)
                        stop-loss-limit (price = stop loss trigger price, price2 = triggered limit price)
                        take-profit-limit (price = take profit trigger price, price2 = triggered limit price)
                        trailing-stop (price = trailing stop offset)
                        trailing-stop-limit (price = trailing stop offset, price2 = triggered limit offset)
                        stop-loss-and-limit (price = stop loss price, price2 = limit price)
                        settle-position
        :param volume: order volume in lots
        :param price: price (optional.  dependent upon ordertype)
        :param price2: secondary price (optional.  dependent upon ordertype)
        :param leverage: amount of leverage desired (default = none)
        :param oflags: comma delimited list of order flags:
                       viqc = volume in quote currency (not available for leveraged orders)
                       fcib = prefer fee in base currency
                       fciq = prefer fee in quote currency
                       nompp = no market price protection
                       post = post only order (available when ordertype = limit)
        :param starttm: scheduled start time:
                        0 = now (default)
                        +<n> = schedule start time <n> seconds from now
                        <n> = unix timestamp of start time
        :param expiretm: expiration time:
                         0 = no expiration (default)
                         +<n> = expire <n> seconds from now
                         <n> = unix timestamp of expiration time
        :param userref: user reference id.  32-bit signed number.
        :param validate: validate inputs only.  do not submit order

        :param close: optional closing order to add to the system when order gets filled:
                      close[ordertype] = order type
                      close[price] = price
                      close[price2] = secondary price
        """
        data = self._create_dict_from_args(pair=pair, type=type, ordertype=ordertype, volume=volume,
                                           price=price, price2=price2, leverage=leverage, oflags=oflags,
                                           starttm=starttm, expiretm=expiretm, userref=userref,
                                           validate=validate, close=close)
        return self._call_private('AddOrder', data=data, inc_call_count=0)

    def cancel_open_order(self, txid):
        """
        :param txid: transaction id
        """
        data = self._create_dict_from_args(txid=txid)
        return self._call_private('CancelOrder', data=data, inc_call_count=0)
