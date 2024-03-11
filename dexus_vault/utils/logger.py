import logging

##TODO: implement normal logging
# handlers = [logging.StreamHandler(sys.stdout)]
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
# logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger()
