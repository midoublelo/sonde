import logging
 
from src.ingestion.weather_client import get_current_weather
from src.storage.db import get_session
from src.storage.models import WeatherSnapshot
 
logger = logging.getLogger(__name__)
 
def poll_and_store_weather() -> None:
    data = get_current_weather()
 
    weather = data["weather"][0]
    main = data["main"]
 
    snapshot = WeatherSnapshot(
        temp_c=main["temp"],
        feels_like_c=main["feels_like"],
        humidity_pct=main["humidity"],
        wind_speed_mps=data["wind"]["speed"],
        weather_main=weather["main"],
        weather_description=weather["description"],
        rain_1h_mm=data.get("rain", {}).get("1h"),
        snow_1h_mm=data.get("snow", {}).get("1h"),
    )
 
    with get_session() as session:
        session.add(snapshot)
 
    logger.info(
        "Stored weather snapshot: %s, %.1fC", weather["description"], main["temp"]
    )