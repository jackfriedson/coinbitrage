
class APIException(Exception):
    pass

class AuthorizationException(APIException):
    pass

class ServiceUnavailableException(APIException):
    pass
