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
        # config['handlers']['order']['filename'] = str(LOG_DIR/'orders.log')
        dictConfig(config)

    # Disable pushclient logger
    logging.getLogger('pusherclient.connection').disabled = True


def getLogger(name: str):
    logger = logging.getLogger(name)
    return BitLoggerAdapter(logger, {'event_name': '', 'event_data': {}})


class BitLoggerAdapter(logging.LoggerAdapter):

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
            formatted_msg = str(msg).format(**self.extra.get('event_data', {}))
        except (IndexError, KeyError):
            formatted_msg = msg
        return formatted_msg, kwargs
