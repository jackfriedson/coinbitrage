from coinbitrage import bitlogging
from coinbitrage.engine import ArbitrageEngine


bitlogging.configure()


EXCHANGES = ['bittrex', 'hitbtc', 'poloniex']


if __name__ == '__main__':
    # engine = ArbitrageEngine(exchanges=EXCHANGES, base_currency='ETH', quote_currency='USDT')
    # engine.run()

    from coinbitrage.exchanges import get_exchange
    kraken = get_exchange('kraken')
    import ipdb; ipdb.set_trace()
