import json
import logging
import sys
from datetime import UTC, datetime

logger = logging.getLogger("dexus_vault")

TEXT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry)


def setup_logging(level: str = "INFO", log_format: str = "text") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter() if log_format == "json" else logging.Formatter(TEXT_FORMAT)
    )
    logger.handlers[:] = [handler]
    logger.setLevel(level)
    logger.propagate = False
    # keep library noise out of our logs
    for name in ("urllib3", "hvac"):
        logging.getLogger(name).setLevel(logging.WARNING)
