from coinbitrage import bitlogging
from coinbitrage.engine import ArbitrageEngine


bitlogging.configure()


EXCHANGES = ['bitstamp', 'coinbase', 'hitbtc', 'poloniex']


if __name__ == '__main__':
    engine = ArbitrageEngine(exchanges=EXCHANGES,
                             base_currency='ETH',
                             quote_currency='BTC',
                             min_base_balance=0.05,
                             min_quote_balance=0.001)
    engine.run()

    # from coinbitrage.exchanges import get_exchange
    # bitstamp = get_exchange('bitstamp')
    # coinbase = get_exchange('coinbase')
    # hitbtc = get_exchange('hitbtc')
    # import ipdb; ipdb.set_trace()
