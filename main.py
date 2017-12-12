from coinbitrage import bitlogging
from coinbitrage.engine import ArbitrageEngine


bitlogging.configure()


EXCHANGES = ['bittrex', 'hitbtc', 'poloniex']


if __name__ == '__main__':
    engine = ArbitrageEngine(exchanges=EXCHANGES,
                             base_currency='ETH',
                             quote_currency='USDT',
                             min_profit=0.005)
    engine.run()
