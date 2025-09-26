import logging
from pathlib import Path

LOG_DIR = Path("output/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_DIR / "pipeline.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

def get_logger(name: str = "academic_translator"):
    return logging.getLogger(name)
