import logging
from datetime import datetime, timezone
 
from src.ingestion.weather_client import get_current_weather
from src.storage.log_store import append_jsonl
 
logger = logging.getLogger(__name__)
 
LOG_PATH = "data/logs/weather.jsonl"

def poll_and_store_weather() -> None:
    data = get_current_weather()
 
    weather = data["weather"][0]
    main = data["main"]
 
    record = {
        "temp_c": main["temp"],
        "feels_like_c": main["feels_like"],
        "humidity_pct": main["humidity"],
        "wind_speed_mps": data["wind"]["speed"],
        "weather_main": weather["main"],
        "weather_description": weather["description"],
        "rain_1h_mm": data.get("rain", {}).get("1h"),
        "snow_1h_mm": data.get("snow", {}).get("1h"),
        "polled_at": datetime.now(timezone.utc).isoformat(),
    }
 
    append_jsonl(LOG_PATH, record)
    logger.info(
        "Appended weather record: %s, %.1fC", weather["description"], main["temp"]
    )