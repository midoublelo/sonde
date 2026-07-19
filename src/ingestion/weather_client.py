import requests
 
from src.config import LONDON_LAT, LONDON_LON, OPENWEATHER_API_KEY, OPENWEATHER_BASE_URL
 
def get_current_weather(lat: float = LONDON_LAT, lon: float = LONDON_LON) -> dict:
    """
    Raw parsed JSON response. Notably: "rain" and "snow" keys are only
    present in the response at all when there's active precipitation -
    callers should use .get() rather than assuming the key exists.
    """
    params = {
        "lat": lat,
        "lon": lon,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
    }
    resp = requests.get(f"{OPENWEATHER_BASE_URL}/weather", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()