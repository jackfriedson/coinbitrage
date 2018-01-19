from requests.exceptions import HTTPError


class ClientError(HTTPError):
    pass

class ExchangeError(Exception):
    pass

class OrderBookUpdateError(Exception):
    pass

class ServerError(HTTPError):
    pass
