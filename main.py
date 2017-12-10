from coinbitrage import bitlogging
from coinbitrage.engine import ArbitrageEngine


bitlogging.configure()


EXCHANGES = ['bitstamp', 'coinbase', 'poloniex']


if __name__ == '__main__':
    engine = ArbitrageEngine(exchanges=EXCHANGES,
                             base_currency='ETH',
                             quote_currency='BTC',
                             min_base_balance=0.05,
                             min_quote_balance=0.001,
                             min_profit=0.)
    engine.run()
