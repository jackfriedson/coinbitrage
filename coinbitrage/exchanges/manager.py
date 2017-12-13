from typing import Dict, List, Union


class ExchangeManager(object):

    def __init__(self, exchanges: List[str]):
        self._clients = {name: get_exchange(name) for name in exchanges}
        self._balances = None
        self._total_balances = {}
        self._last_bid_ask = {exchg: {'bid': None, 'ask': None, 'time': None} for exchg in exchanges}

    def last_bid_ask(self, exchange: str = None) -> Union[Dict[str, Dict[str, float]], Dict[str, float]]:
        pass

    def last_bid(self, exchange: str = None) -> Union[Dict[str, float], float]:
        pass

    def last_ask(self, exchange: str = None) -> Union[Dict[str, float], float]:
        pass

    def balances(self):
        pass

    def transfer_to_trading_accounts(self, currency: str):
        for exchange in self._clients.values():
            if isinstance(exchange.api, SeparateTradingAccountMixin):
                bank_balance = exchange.bank_balance()[currency]

                if bank_balance > 0:
                    exchange.bank_to_trading(currency, bank_balance)

    def redistribute(currency: str):
        total_balance = self._total_balances[currency]
        order_size = CURRENCIES[currency]['order_size']
        average_balance = (total_balance - order_size) / len(self._exchanges)
        min_transfer = CURRENCIES[currency]['min_transfer_size']

        debts = {}
        credits = {}

        for exchg, balances in self._exchange_balances.items():
            balance = balances[currency]
            if balance < order_size:
                debts[exchg] = average_balance - balance
            elif balance > average_balance + min_transfer:
                credits[exchg] = balance - average_balance

        log.debug('{} debts: {}'.format(currency, debts))
        log.debug('{} credits: {}'.format(currency, credits))

        try:
            while debts and credits:
                to_exchange, debt = max(debts.items(), key=lambda x: x[1])
                from_exchange, credit = max(credits.items(), key=lambda x: x[1])
                to_exchange_client = self._exchanges[to_exchange]
                from_exchange_client = self._exchanges[from_exchange]

                if debt < credit:
                    transfer_amt = max(debt, min_transfer)
                    to_exchange_client.get_funds_from(from_exchange_client, currency, transfer_amt)
                    debts.pop(to_exchange)
                    credits[from_exchange] = credit - transfer_amt
                    if credits[from_exchange] < min_transfer:
                        credits.pop(from_exchange)
                else:
                    assert credit >= min_transfer
                    to_exchange_client.get_funds_from(from_exchange_client, currency, credit)
                    credits.pop(from_exchange)
                    debts[to_exchange] = debt - credit
        except RequestException as e:
            log.warning('Could not successfully redistribute funds', event_name='redistribute_funds.failure',
                        event_data={'exception': e})
