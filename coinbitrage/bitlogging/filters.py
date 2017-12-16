import logging


class EventNameFilter(logging.Filter):

    def __init__(self, contains: str = None):
        # TODO: add support for other operations (e.g. equals, startswith, etc.)
        super(EventNameFilter, self).__init__()
        self._contains = contains

    def filter(self, record: logging.LogRecord) -> bool:
        return self._contains in record.event_name.split('.')
