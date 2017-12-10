from coinbitrage import bitlogging
from coinbitrage.engine import ArbitrageEngine


bitlogging.configure()


EXCHANGES = ['bitstamp', 'coinbase', 'hitbtc', 'poloniex']


if __name__ == '__main__':
    engine = ArbitrageEngine(exchanges=EXCHANGES, base_currency='ETH', quote_currency='BTC')
    engine.run()
