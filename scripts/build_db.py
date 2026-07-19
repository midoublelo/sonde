"""
Rebuilds the local SQLite database from the git-tracked logs
(data/logs/tube_status.jsonl and data/logs/weather.jsonl). The logs are
the source of truth now; the SQLite file is a disposable, locally-built
query cache that's no longer committed to git (see .gitignore).

Run this after `git pull` (whenever the logs might have new data), and
before using the dashboard, sanity check, or journey planner's --live
flag. It's a full rebuild every time, not an incremental update -
simplest correctness guarantee, and at this project's data volume
(a poll every 15 min) it'll stay fast for a very long time.

Deduplicates defensively: if the same (line_id, polled_at) or weather
polled_at appears more than once (e.g. two overlapping runs happened to
poll at the exact same moment), only one copy is kept - a poll being
logged twice is a much safer failure mode than a poll being lost.

Usage:
    python -m scripts.build_db_from_logs
"""
from datetime import datetime

from src.storage.db import get_session, init_db
from src.storage.log_store import read_jsonl
from src.storage.models import LineStatusSnapshot, WeatherSnapshot

TUBE_LOG_PATH = "data/logs/tube_status.jsonl"
WEATHER_LOG_PATH = "data/logs/weather.jsonl"


def _dedupe(records: list[dict], key_fields: tuple) -> list[dict]:
    seen = {}
    for r in records:
        key = tuple(r.get(f) for f in key_fields)
        seen[key] = r  # last write wins, but records are near-identical anyway
    return list(seen.values())


def rebuild() -> tuple[int, int]:
    init_db()

    tube_records = _dedupe(read_jsonl(TUBE_LOG_PATH), ("line_id", "polled_at"))
    weather_records = _dedupe(read_jsonl(WEATHER_LOG_PATH), ("polled_at",))

    with get_session() as session:
        # Full rebuild: clear existing rows, re-insert from the logs.
        session.query(LineStatusSnapshot).delete()
        session.query(WeatherSnapshot).delete()

        for r in tube_records:
            session.add(
                LineStatusSnapshot(
                    line_id=r["line_id"],
                    line_name=r["line_name"],
                    status_severity=r["status_severity"],
                    status_description=r["status_description"],
                    reason=r.get("reason"),
                    polled_at=datetime.fromisoformat(r["polled_at"]),
                )
            )

        for r in weather_records:
            session.add(
                WeatherSnapshot(
                    temp_c=r["temp_c"],
                    feels_like_c=r["feels_like_c"],
                    humidity_pct=r["humidity_pct"],
                    wind_speed_mps=r["wind_speed_mps"],
                    weather_main=r["weather_main"],
                    weather_description=r["weather_description"],
                    rain_1h_mm=r.get("rain_1h_mm"),
                    snow_1h_mm=r.get("snow_1h_mm"),
                    polled_at=datetime.fromisoformat(r["polled_at"]),
                )
            )

    return len(tube_records), len(weather_records)


if __name__ == "__main__":
    tube_count, weather_count = rebuild()
    print(f"Rebuilt local DB: {tube_count} tube status rows, {weather_count} weather rows")