import sys
import logging

from dexus_vault.utils.config import GeneralConfig

general_config = GeneralConfig()

# Define a format for your logs
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Create a stream handler
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(general_config.log_level)
stream_handler.setFormatter(logging.Formatter(log_format))

# Get a logger
logger = logging.getLogger("dexus_vault")
logger.setLevel(general_config.log_level)

# Add the handlers to the logger
logger.addHandler(stream_handler)
# logger.addHandler(file_handler)

# Set log level for external libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
