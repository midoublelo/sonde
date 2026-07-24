from collections import defaultdict
from datetime import datetime

import pandas as pd
from sqlalchemy import select

from src.storage.db import get_session
from src.storage.models import LineStatusSnapshot, WeatherSnapshot

def load_status_history() -> pd.DataFrame:
    with get_session() as session:
        rows = session.execute(
            select(LineStatusSnapshot).order_by(LineStatusSnapshot.polled_at)
        ).scalars().all()
        data = [
            {
                "line_id": r.line_id,
                "line_name": r.line_name,
                "status_severity": r.status_severity,
                "status_description": r.status_description,
                "reason": r.reason,
                "polled_at": r.polled_at,
            }
            for r in rows
        ]
    df = pd.DataFrame(data)
    if not df.empty:
        df["polled_at"] = pd.to_datetime(df["polled_at"], utc=True)
        df["is_good"] = df["status_description"].str.strip().str.lower() == "good service"
    return df

def load_weather_history() -> pd.DataFrame:
    with get_session() as session:
        rows = session.execute(
            select(WeatherSnapshot).order_by(WeatherSnapshot.polled_at)
        ).scalars().all()
        data = [
            {
                "temp_c": r.temp_c,
                "weather_main": r.weather_main,
                "weather_description": r.weather_description,
                "rain_1h_mm": r.rain_1h_mm,
                "polled_at": r.polled_at,
            }
            for r in rows
        ]
    df = pd.DataFrame(data)
    if not df.empty:
        df["polled_at"] = pd.to_datetime(df["polled_at"], utc=True)
    return df

def reliability_scoreboard(status_df: pd.DataFrame) -> pd.DataFrame:
    if status_df.empty:
        return pd.DataFrame()

    records = []
    for line_name, group in status_df.sort_values("polled_at").groupby("line_name"):
        good_series = group["is_good"].tolist()
        polls = len(good_series)
        pct_good = 100 * sum(good_series) / polls if polls else 0

        disruption_count = 0
        longest_streak = 0
        current_streak = 0
        prev_good = True
        for is_good in good_series:
            if not is_good:
                if prev_good:
                    disruption_count += 1
                current_streak += 1
                longest_streak = max(longest_streak, current_streak)
            else:
                current_streak = 0
            prev_good = is_good

        records.append(
            {
                "Line": line_name,
                "Polls": polls,
                "% Good Service": round(pct_good, 1),
                "Disruption episodes": disruption_count,
                "Longest disrupted streak": longest_streak,
            }
        )

    return pd.DataFrame(records).sort_values("% Good Service").reset_index(drop=True)

def status_timeline(status_df: pd.DataFrame) -> pd.DataFrame:
    if status_df.empty:
        return pd.DataFrame()
    return status_df.pivot_table(
        index="polled_at",
        columns="line_name",
        values="status_severity",
        aggfunc="last",
    )

_CATEGORY_ORDER = ["Closed", "Suspended", "Disrupted", "Minor", "Good Service"]

_EXACT_CATEGORY = {
    "good service": "Good Service",
    "minor delays": "Minor",
    "severe delays": "Disrupted",
    "part closure": "Disrupted",
    "part suspended": "Suspended",
    "suspended": "Suspended",
    "service closed": "Closed",
    "planned closure": "Closed",
}

_FALLBACK_RULES = [
    ("Closed", ["closed", "closure"]),
    ("Suspended", ["suspended", "no service"]),
    ("Minor", ["minor"]),
    ("Disrupted", ["severe", "delays", "reduced", "special", "part", "bus"]),
    ("Good Service", ["good service"]),
]

def categorize_status(description: str) -> str:
    if not description:
        return "Disrupted"
    text = description.strip().lower()

    if text in _EXACT_CATEGORY:
        return _EXACT_CATEGORY[text]
    for category, needles in _FALLBACK_RULES:
        if any(n in text for n in needles):
            return category
    return "Disrupted"

def status_timeline_categorical(status_df: pd.DataFrame) -> pd.DataFrame:
    if status_df.empty:
        return pd.DataFrame()
    df = status_df.copy()
    df["category"] = df["status_description"].apply(categorize_status)
    return df[["polled_at", "line_name", "category"]]

def weather_disruption_crosstab(status_df: pd.DataFrame, weather_df: pd.DataFrame) -> pd.DataFrame:
    if status_df.empty or weather_df.empty:
        return pd.DataFrame()

    status = status_df.copy()
    status["category"] = status["status_description"].apply(categorize_status)
    status["is_disrupted"] = status["category"] != "Good Service"

    status = status.sort_values("polled_at")
    weather = weather_df.sort_values("polled_at")[["polled_at", "weather_main"]]

    joined = pd.merge_asof(
        status,
        weather,
        on="polled_at",
        direction="nearest",
        tolerance=pd.Timedelta("30min"),
    )
    joined = joined.dropna(subset=["weather_main"])
    if joined.empty:
        return pd.DataFrame()

    summary = (
        joined.groupby("weather_main")
        .agg(
            observations=("is_disrupted", "size"),
            disrupted=("is_disrupted", "sum"),
        )
        .reset_index()
    )
    summary["% disrupted"] = round(
        100 * summary["disrupted"] / summary["observations"], 1
    )
    summary = summary.rename(
        columns={"weather_main": "Weather", "observations": "Observations",
                 "disrupted": "Disrupted count"}
    )
    return summary.sort_values("% disrupted", ascending=False).reset_index(drop=True)

def affected_stations(status_df: pd.DataFrame, graph) -> pd.DataFrame:
    if status_df.empty:
        return pd.DataFrame()

    status = status_df.copy()
    status["category"] = status["status_description"].apply(categorize_status)
    status["is_disrupted"] = status["category"] != "Good Service"

    disrupted = status[status["is_disrupted"]]
    if disrupted.empty:
        return pd.DataFrame()

    stations_by_line = {}
    for u, v, data in graph.edges(data=True):
        line_id = data["line"]
        stations_by_line.setdefault(line_id, set()).update([u, v])

    counts = {}
    for _, row in disrupted.iterrows():
        for station_id in stations_by_line.get(row["line_id"], ()):
            counts[station_id] = counts.get(station_id, 0) + 1

    records = []
    for station_id, count in counts.items():
        node = graph.nodes[station_id]
        records.append(
            {
                "station_id": station_id,
                "name": node.get("name", station_id),
                "lat": node.get("lat"),
                "lon": node.get("lon"),
                "affected_polls": count,
            }
        )

    df = pd.DataFrame(records)
    return df.sort_values("affected_polls", ascending=False).reset_index(drop=True)