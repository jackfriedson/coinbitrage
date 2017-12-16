import cmd

from coinbitrage.exchanges.manager import ExchangeManager


class CoinbitrageShell(cmd.Cmd):
    intro = 'Welcome to the Coinbitrage shell. Type help or ? to list available commands.\n'
    prompt = '> '
    file = None

    def __init__(self, exchanges, *args, **kwargs):
        self._exchanges = ExchangeManager(exchanges)
        super(CoinbitrageShell, self).__init__(*args, **kwargs)
