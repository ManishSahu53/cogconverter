import logging
import os

from cogconverter.config import config
from cogconverter.config import logging_config


# Configure logger for use in package
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging_config.get_console_handler())
logger.propagate = False


with open('VERSION') as version_file:
    __version__=version_file.read().strip()
