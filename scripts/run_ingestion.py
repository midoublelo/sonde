import logging
 
from src.ingestion.poller import poll_and_store
from src.ingestion.weather_poller import poll_and_store_weather
 
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
 
if __name__ == "__main__":
    try:
        poll_and_store()
    except Exception:
        logger.exception("Tube status ingestion failed")
 
    try:
        poll_and_store_weather()
    except Exception:
        logger.exception("Weather ingestion failed")
 