import logging
import os

from cogconverter.config import default_config
from cogconverter.config import logging_config
import cogconverter.validator
import  cogconverter.converter


# Configure logger for use in package
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging_config.get_console_handler())
logger.propagate = False


with open('./VERSION') as version_file:
    __version__=version_file.read().strip()