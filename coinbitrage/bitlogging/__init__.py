import logging
from logging.config import dictConfig
from pathlib import Path

import yaml

from .adapters import BitLoggerAdapter
from .filters import EventNameFilter
from .formatters import BitLogFormatter, JSONFormatter, OrderFormatter


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
