from coinbitrage import bitlogging
from coinbitrage.engine import ArbitrageEngine


bitlogging.configure()


EXCHANGES = ['bittrex', 'hitbtc', 'poloniex']


if __name__ == '__main__':
    engine = ArbitrageEngine(exchanges=EXCHANGES, base_currency='BCH', quote_currency='ETH')
    engine.run()
