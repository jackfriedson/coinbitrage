from requests.exceptions import HTTPError


class ClientError(HTTPError):
    pass

class ServerError(HTTPError):
    pass
