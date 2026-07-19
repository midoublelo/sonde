"""
One-time migration for anyone who already has a tube.db with real
ingested data from before this switch to log-based storage. Reads every
existing row out of the SQLite DB and appends it to the new JSON-lines
logs, so the hours of data already collected aren't thrown away.

Safe to run even if data/tube.db doesn't exist or is empty - it'll just
report 0 rows migrated.

Usage:
    python -m scripts.migrate_existing_db
"""
from sqlalchemy import select

from src.storage.db import get_session
from src.storage.log_store import append_jsonl
from src.storage.models import LineStatusSnapshot, WeatherSnapshot

TUBE_LOG_PATH = "data/logs/tube_status.jsonl"
WEATHER_LOG_PATH = "data/logs/weather.jsonl"


def migrate() -> tuple[int, int]:
    with get_session() as session:
        tube_rows = session.execute(select(LineStatusSnapshot)).scalars().all()
        weather_rows = session.execute(select(WeatherSnapshot)).scalars().all()

        for r in tube_rows:
            append_jsonl(
                TUBE_LOG_PATH,
                {
                    "line_id": r.line_id,
                    "line_name": r.line_name,
                    "status_severity": r.status_severity,
                    "status_description": r.status_description,
                    "reason": r.reason,
                    "polled_at": r.polled_at.isoformat(),
                },
            )

        for r in weather_rows:
            append_jsonl(
                WEATHER_LOG_PATH,
                {
                    "temp_c": r.temp_c,
                    "feels_like_c": r.feels_like_c,
                    "humidity_pct": r.humidity_pct,
                    "wind_speed_mps": r.wind_speed_mps,
                    "weather_main": r.weather_main,
                    "weather_description": r.weather_description,
                    "rain_1h_mm": r.rain_1h_mm,
                    "snow_1h_mm": r.snow_1h_mm,
                    "polled_at": r.polled_at.isoformat(),
                },
            )

    return len(tube_rows), len(weather_rows)


if __name__ == "__main__":
    tube_count, weather_count = migrate()
    print(
        f"Migrated {tube_count} tube status row(s) and {weather_count} "
        f"weather row(s) from data/tube.db into the new logs."
    )
    print(
        "Next: commit and push data/logs/*.jsonl, then you can stop "
        "tracking data/tube.db in git (it's now gitignored going forward)."
    )