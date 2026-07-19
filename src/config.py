import os
from dotenv import load_dotenv

load_dotenv()
 
TFL_APP_KEY = os.getenv("TFL_APP_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/tube.db")
 
TFL_BASE_URL = "https://api.tfl.gov.uk"
 
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"
 
# Central London (Trafalgar Square) - one weather reading is a reasonable
# proxy for the whole network at this project's scale. Revisit if a
# later phase wants per-zone weather granularity.
LONDON_LAT = 51.5074
LONDON_LON = -0.1278