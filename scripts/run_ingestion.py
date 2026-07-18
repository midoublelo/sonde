import logging

from src.ingestion.poller import poll_and_store
from src.storage.db import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

if __name__ == "__main__":
    init_db()  # no-op if tables already exist
    poll_and_store()
