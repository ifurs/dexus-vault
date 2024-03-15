import os
import sys
import logging


log_level = os.getenv("LOG_LEVEL", "INFO")
# Define a format for your logs
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Create a stream handler
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(log_level)
stream_handler.setFormatter(logging.Formatter(log_format))

## Create a file handler
# file_handler = logging.FileHandler('dexus_vault.log')
# file_handler.setLevel(log_level)
# file_handler.setFormatter(logging.Formatter(log_format))

# Get a logger
logger = logging.getLogger("dexus_vault")
logger.setLevel(log_level)

# Add the handlers to the logger
logger.addHandler(stream_handler)
# logger.addHandler(file_handler)

# Set log level for external libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
