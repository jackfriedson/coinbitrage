from coinbitrage import settings

from .bitstamp import BitstampClient as Bitstamp
from .bitfinex import BitfinexClient as Bitfinex
from .bittrex import BittrexClient as Bittrex
from .coinbase import CoinbaseClient as Coinbase
from .hitbtc import HitBtcClient as HitBtc
from .kraken import KrakenClient as Kraken
from .poloniex import PoloniexClient as Poloniex


_exchange_map = {
    'bitfinex': Bitfinex,
    'bitstamp': Bitstamp,
    'bittrex': Bittrex,
    'coinbase': Coinbase,
    'hitbtc': HitBtc,
    'kraken': Kraken,
    'poloniex': Poloniex
}


def get_exchange(name: str):
    """Gets the REST API adapter for the specified exchange.

    :param name: The name of the exchange
    """
    name = name.lower()
    api_key = str(settings.API_KEY_DIR/f'{name}.key')
    kwargs = {}

    if name == 'coinbase':
        kwargs['gdax_key_file'] = str(settings.API_KEY_DIR/'gdax.key')

    return _exchange_map[name](api_key, **kwargs)
