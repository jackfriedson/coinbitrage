import json
import logging
from collections import defaultdict
from logging.config import dictConfig
from pathlib import Path

import yaml


LOG_DIR = Path().resolve()/'logs'
LOG_DIR.mkdir(exist_ok=True)
CONFIG_FILE = Path().resolve()/'log_config.yaml'


def configure():
    with CONFIG_FILE.open('rt') as f:
        config = yaml.safe_load(f.read())
        config['handlers']['file']['filename'] = str(LOG_DIR/'all.log')
        config['handlers']['order']['filename'] = str(LOG_DIR/'orders.log')
        dictConfig(config)

    # Disable pushclient logger
    logging.getLogger('pusherclient.connection').disabled = True


def getLogger(name: str):
    return BitLoggerAdapter(logging.getLogger(name))


class BitLoggerAdapter(logging.LoggerAdapter):

    def __init__(self, logger):
        super(BitLoggerAdapter, self).__init__(logger, {'event_name': '', 'event_data': {}})

    def log(self, level, msg, *args, **kwargs):
        if self.isEnabledFor(level):
            self.extra = {'event_name': '', 'event_data': {}}
            if 'event_name' in kwargs:
                self.extra['event_name'] = kwargs.pop('event_name')
            if 'event_data' in kwargs:
                self.extra['event_data'] = kwargs.pop('event_data')

            msg, kwargs = self.process(msg, kwargs)
            self.logger._log(level, msg, args, **kwargs)

    def process(self, msg, kwargs):
        msg, kwargs = super(BitLoggerAdapter, self).process(msg, kwargs)
        try:
            # TODO: Move this to a custom formatter
            formatted_msg = str(msg).format(**self.extra.get('event_data', {}))
        except (IndexError, KeyError):
            formatted_msg = msg
        return formatted_msg, kwargs


class EventNameFilter(logging.Filter):

    def __init__(self, contains: str = None):
        # TODO: add support for other operations (e.g. equals, startswith, etc.)
        self._contains = contains
        super(EventNameFilter, self).__init__()

    def filter(self, record: logging.LogRecord) -> bool:
        return self._contains in record.event_name.split('.')


class OrderFormatter(logging.Formatter):
    _fmt = '{asctime} {event_name:20} -- {exchange} {side} ' + \
           '{volume} {base} @ {price} {quote}{order_id}'

    def format(self, record: logging.LogRecord) -> str:
        asctime = self.formatTime(record, datefmt='%Y-%m-%d %H:%M:%S')
        order_id = record.event_data.pop('order_id', None)
        order_id_str = ' ({})'.format(order_id) if order_id else ''
        return self._fmt.format(asctime=asctime, event_name=record.event_name,
                                order_id=order_id_str, **record.event_data)


class JSONFormatter(logging.Formatter):

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(record.__dict__)
