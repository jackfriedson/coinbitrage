from coinbitrage import bitlogging
from coinbitrage.engine import ArbitrageEngine


bitlogging.configure()


EXCHANGES = ['bitstamp', 'coinbase', 'hitbtc', 'poloniex']


if __name__ == '__main__':
    engine = ArbitrageEngine(exchanges=['bittrex', 'hitbtc'], base_currency='ETH', quote_currency='BTC')
    engine.run()

    # from coinbitrage.exchanges import get_exchange
    # hitbtc = get_exchange('hitbtc')
    # bittrex = get_exchange('bittrex')
    # import ipdb; ipdb.set_trace()
