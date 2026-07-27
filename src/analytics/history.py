from collections import defaultdict
from datetime import datetime

import pandas as pd
from sqlalchemy import select

from src.storage.db import get_session
from src.storage.models import LineStatusSnapshot, WeatherSnapshot

_MIN_OBSERVATIONS_FOR_ANOMALY = 8

_ANOMALY_RATE_THRESHOLD = 15.0

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
        descs = group["status_description"].tolist()
        polls = len(descs)
        # "Disrupted" now means unplanned only - scheduled closures don't count.
        disrupted_flags = [is_unplanned_disruption(d) for d in descs]
        pct_disrupted = 100 * sum(disrupted_flags) / polls if polls else 0

        disruption_count = 0
        longest_streak = 0
        current_streak = 0
        prev_disrupted = False
        for flag in disrupted_flags:
            if flag:
                if not prev_disrupted:
                    disruption_count += 1
                current_streak += 1
                longest_streak = max(longest_streak, current_streak)
            else:
                current_streak = 0
            prev_disrupted = flag

        records.append({
            "Line": line_name,
            "Polls": polls,
            "% Unplanned disruption": round(pct_disrupted, 1),
            "Disruption episodes": disruption_count,
            "Longest disrupted streak": longest_streak,
        })

    return pd.DataFrame(records).sort_values(
        "% Unplanned disruption", ascending=False
    ).reset_index(drop=True)

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

_UNPLANNED_DISRUPTION = {"Minor", "Disrupted", "Suspended"}

# Note: "Part Closure" maps to "Disrupted" in _EXACT_CATEGORY but is
# planned - so we override it here by description rather than category.
_PLANNED_DESCRIPTIONS = {"planned closure", "part closure", "service closed"}


def is_unplanned_disruption(description: str) -> bool:
    """
    True only for genuine unplanned disruption. Excludes scheduled
    closures even though some share a category with disruptions
    (Part Closure -> Disrupted category, but it's planned).
    """
    if not description:
        return False
    if description.strip().lower() in _PLANNED_DESCRIPTIONS:
        return False
    return categorize_status(description) in _UNPLANNED_DISRUPTION

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
    status["is_disrupted"] = status["status_description"].apply(is_unplanned_disruption)

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

def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    local = out["polled_at"].dt.tz_convert("Europe/London")
    out["hour"] = local.dt.hour
    out["dayofweek"] = local.dt.dayofweek           # 0 = Monday
    out["is_weekend"] = out["dayofweek"] >= 5
    out["is_disrupted"] = out["status_description"].apply(is_unplanned_disruption)
    return out


def disruption_rate_by(df: pd.DataFrame, *group_cols) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    featured = add_time_features(df)
    grouped = (
        featured.groupby(list(group_cols))
        .agg(
            observations=("is_disrupted", "size"),
            disruptions=("is_disrupted", "sum"),
        )
        .reset_index()
    )
    grouped["rate_pct"] = round(
        100 * grouped["disruptions"] / grouped["observations"], 1
    )
    return grouped

def detect_anomalies(status_df: pd.DataFrame) -> pd.DataFrame:
    """
    Flag CURRENTLY-disrupted lines that are disrupted at an hour when
    they're historically reliable. Compares each line's current status
    against its own line x hour baseline (from disruption_rate_by).

    Returns one row per currently-disrupted line with: line, current
    status, this hour's historical rate, observations behind that rate,
    and a verdict (Anomalous / Expected / Insufficient data).

    Empty if nothing is currently disrupted.
    """
    if status_df.empty:
        return pd.DataFrame()

    featured = add_time_features(status_df)

    # Current status = each line's most recent observation.
    latest = featured.sort_values("polled_at").groupby("line_id").last().reset_index()
    currently_disrupted = latest[latest["is_disrupted"]]
    if currently_disrupted.empty:
        return pd.DataFrame()

    # Historical line x hour baseline.
    baseline = disruption_rate_by(status_df, "line_id", "hour")

    records = []
    for _, row in currently_disrupted.iterrows():
        line_id = row["line_id"]
        hour = row["hour"]
        bucket = baseline[
            (baseline["line_id"] == line_id) & (baseline["hour"] == hour)
        ]

        if bucket.empty:
            rate, obs = None, 0
        else:
            rate = float(bucket.iloc[0]["rate_pct"])
            obs = int(bucket.iloc[0]["observations"])

        if obs < _MIN_OBSERVATIONS_FOR_ANOMALY:
            verdict = "Insufficient data"
        elif rate <= _ANOMALY_RATE_THRESHOLD:
            verdict = "Anomalous"
        else:
            verdict = "Expected"

        records.append(
            {
                "Line": row["line_name"],
                "Current status": row["status_description"],
                "Hour": int(hour),
                "Historical rate this hour (%)": rate if rate is not None else "—",
                "Observations": obs,
                "Verdict": verdict,
            }
        )

    # Sort so genuine anomalies surface to the top.
    order = {"Anomalous": 0, "Insufficient data": 1, "Expected": 2}
    return (
        pd.DataFrame(records)
        .assign(_o=lambda d: d["Verdict"].map(order))
        .sort_values("_o")
        .drop(columns="_o")
        .reset_index(drop=True)
    )