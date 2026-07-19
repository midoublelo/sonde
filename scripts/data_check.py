import pandas as pd
from sqlalchemy import select
 
from src.graph.tube_graph import load_graph
from src.storage.db import get_session
from src.storage.models import LineStatusSnapshot, WeatherSnapshot
 
GRAPH_PATH = "data/tube_graph.json"
EXPECTED_POLL_INTERVAL_MINUTES = 15
GAP_THRESHOLD_MINUTES = 25  # a bit more than one interval, to allow slack
 
_LINE_COLUMNS = [
    "line_id",
    "line_name",
    "status_severity",
    "status_description",
    "reason",
    "polled_at",
]
 
_WEATHER_COLUMNS = [
    "temp_c",
    "feels_like_c",
    "humidity_pct",
    "wind_speed_mps",
    "weather_main",
    "weather_description",
    "rain_1h_mm",
    "snow_1h_mm",
    "polled_at",
]

def load_snapshots_df() -> pd.DataFrame:
    with get_session() as session:
        rows = session.execute(select(LineStatusSnapshot)).scalars().all()
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
    df = pd.DataFrame(data, columns=_LINE_COLUMNS)
    if not df.empty:
        df["polled_at"] = pd.to_datetime(df["polled_at"], utc=True)
    return df

def load_weather_df() -> pd.DataFrame:
    with get_session() as session:
        rows = session.execute(select(WeatherSnapshot)).scalars().all()
        data = [
            {
                "temp_c": r.temp_c,
                "feels_like_c": r.feels_like_c,
                "humidity_pct": r.humidity_pct,
                "wind_speed_mps": r.wind_speed_mps,
                "weather_main": r.weather_main,
                "weather_description": r.weather_description,
                "rain_1h_mm": r.rain_1h_mm,
                "snow_1h_mm": r.snow_1h_mm,
                "polled_at": r.polled_at,
            }
            for r in rows
        ]
    df = pd.DataFrame(data, columns=_WEATHER_COLUMNS)
    if not df.empty:
        df["polled_at"] = pd.to_datetime(df["polled_at"], utc=True)
    return df

def print_overview(df: pd.DataFrame, label: str = "TUBE STATUS") -> None:
    print("=" * 60)
    print(f"{label} OVERVIEW")
    print("=" * 60)
    if df.empty:
        print("No data at all yet - nothing has been ingested.")
        return
 
    earliest = df["polled_at"].min()
    latest = df["polled_at"].max()
    span = latest - earliest
    distinct_polls = df["polled_at"].nunique()
    expected_polls = max(
        int(span.total_seconds() / 60 / EXPECTED_POLL_INTERVAL_MINUTES), 1
    )
 
    print(f"Total rows:          {len(df)}")
    print(f"Distinct poll times: {distinct_polls}")
    print(f"Earliest poll:       {earliest}")
    print(f"Latest poll:         {latest}")
    print(f"Time span:           {span}")
    print(
        f"Expected ~polls:     {expected_polls} "
        f"(at one every {EXPECTED_POLL_INTERVAL_MINUTES} min)"
    )
    if distinct_polls < expected_polls * 0.7:
        print("  -> Fewer polls than expected for this time span - see gap check below.")

def print_per_line_breakdown(df: pd.DataFrame) -> None:
    print()
    print("=" * 60)
    print("PER-LINE BREAKDOWN")
    print("=" * 60)
    if df.empty:
        return
 
    for line_name, group in df.groupby("line_name"):
        total = len(group)
        good = (group["status_description"].str.lower() == "good service").sum()
        pct_good = 100 * good / total if total else 0
        distinct_statuses = group["status_description"].nunique()
        print(
            f"{line_name:20s} {total:5d} snapshots  "
            f"{pct_good:5.1f}% Good Service  {distinct_statuses} distinct status type(s)"
        )

def find_gaps(poll_times: list) -> list[tuple]:
    """Source-agnostic: works on any sorted list of poll timestamps."""
    gaps = []
    for prev, curr in zip(poll_times, poll_times[1:]):
        gap_minutes = (curr - prev) / pd.Timedelta(minutes=1)
        if gap_minutes > GAP_THRESHOLD_MINUTES:
            gaps.append((prev, curr, gap_minutes))
    return gaps

def print_gap_report(df: pd.DataFrame, label: str = "TUBE STATUS") -> None:
    print()
    print("=" * 60)
    print(f"{label} GAP CHECK (flagging gaps > {GAP_THRESHOLD_MINUTES} min)")
    print("=" * 60)
    if df.empty:
        print("No data to check.")
        return
 
    poll_times = sorted(df["polled_at"].unique())
    gaps = find_gaps(poll_times)
 
    if not gaps:
        print("No gaps found - ingestion looks continuous.")
        return
 
    print(f"Found {len(gaps)} gap(s):")
    for prev, curr, gap_minutes in gaps:
        print(f"  {prev} -> {curr}  ({gap_minutes:.0f} min gap)")

def print_weather_overview(df: pd.DataFrame) -> None:
    print()
    print_overview(df, label="WEATHER")
    if df.empty:
        return
 
    avg_temp = df["temp_c"].mean()
    rain_polls = df["rain_1h_mm"].notna().sum()
    snow_polls = df["snow_1h_mm"].notna().sum()
    print(f"Average temp:        {avg_temp:.1f}C")
    print(f"Polls with rain:     {rain_polls} ({100 * rain_polls / len(df):.0f}%)")
    print(f"Polls with snow:     {snow_polls} ({100 * snow_polls / len(df):.0f}%)")
    print(f"Conditions seen:     {', '.join(sorted(df['weather_main'].unique()))}")

def print_source_comparison(tube_df: pd.DataFrame, weather_df: pd.DataFrame) -> None:
    """
    Catches the specific failure mode where run_ingestion.py's per-source
    try/except (see scripts/run_ingestion.py) lets one source silently
    fail run after run while the other keeps succeeding - which shows as
    a perfectly green GitHub Action the whole time. Comparing distinct
    poll counts between the two tables is the one place that failure
    actually becomes visible.
    """
    print()
    print("=" * 60)
    print("CROSS-SOURCE COMPARISON")
    print("=" * 60)
 
    tube_polls = tube_df["polled_at"].nunique() if not tube_df.empty else 0
    weather_polls = weather_df["polled_at"].nunique() if not weather_df.empty else 0
 
    print(f"Tube status distinct polls:  {tube_polls}")
    print(f"Weather distinct polls:      {weather_polls}")
 
    if tube_polls == 0:
        return  # nothing to compare against yet
 
    if weather_polls == 0 and tube_polls > 0:
        print(
            "  -> Weather has NEVER succeeded while Tube status has. Since "
            "each source fails independently and silently (by design - "
            "see run_ingestion.py), this won't show up as a failed Action "
            "run. Check the 'Run ingestion' step's log output for a "
            "'Weather ingestion failed' traceback - a 401 Unauthorized "
            "error there usually just means a freshly-created OpenWeatherMap "
            "key hasn't activated yet (can take a couple of hours)."
        )
    elif weather_polls < tube_polls * 0.7:
        print(
            f"  -> Weather is falling behind Tube status ({weather_polls} vs "
            f"{tube_polls} polls) - check the Action logs for intermittent "
            "weather failures."
        )
    else:
        print("  -> Both sources are keeping pace with each other.")

def print_missing_lines(df: pd.DataFrame) -> None:
    print()
    print("=" * 60)
    print("MISSING LINES CHECK (against the network graph)")
    print("=" * 60)
    try:
        graph = load_graph(GRAPH_PATH)
    except FileNotFoundError:
        print(f"No graph found at {GRAPH_PATH} - run build_graph.py to enable this check.")
        return
 
    expected_line_ids = {data["line"] for _, _, data in graph.edges(data=True)}
    seen_line_ids = set(df["line_id"]) if not df.empty else set()
    missing = expected_line_ids - seen_line_ids
 
    if not missing:
        print(f"All {len(expected_line_ids)} line(s) from the graph have shown up in ingested data.")
    else:
        print(f"{len(missing)} line(s) in the graph have never appeared in ingested data:")
        for line_id in sorted(missing):
            print(f"  - {line_id}")
        print(
            "(Could just mean no data yet, or a line-id mismatch between "
            "the graph and the status endpoint - worth checking if it "
            "persists once you have several hours of data.)"
        )

def main() -> None:
    tube_df = load_snapshots_df()
    weather_df = load_weather_df()
 
    print_overview(tube_df, label="TUBE STATUS")
    print_per_line_breakdown(tube_df)
    print_gap_report(tube_df, label="TUBE STATUS")
    print_missing_lines(tube_df)
 
    print_weather_overview(weather_df)
    print_gap_report(weather_df, label="WEATHER")
 
    print_source_comparison(tube_df, weather_df)
 
 
if __name__ == "__main__":
    main()