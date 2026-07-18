import os
from dotenv import load_dotenv

load_dotenv()

TFL_APP_KEY = os.getenv("TFL_APP_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/tube.db")

TFL_BASE_URL = "https://api.tfl.gov.uk"