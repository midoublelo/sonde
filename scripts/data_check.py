import pandas as pd
from sqlalchemy import select

from src.graph.tube_graph import load_graph
from src.storage.db import get_session
from src.storage.models import LineStatusSnapshot

GRAPH_PATH = "data/tube_graph.json"
EXPECTED_POLL_INTERVAL_MINUTES = 15
GAP_THRESHOLD_MINUTES = 25  # a bit more than one interval, to allow slack

_COLUMNS = [
    "line_id",
    "line_name",
    "status_severity",
    "status_description",
    "reason",
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
    df = pd.DataFrame(data, columns=_COLUMNS)
    if not df.empty:
        df["polled_at"] = pd.to_datetime(df["polled_at"], utc=True)
    return df

def print_overview(df: pd.DataFrame) -> None:
    print("=" * 60)
    print("OVERVIEW")
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

def print_gap_report(df: pd.DataFrame) -> None:
    print()
    print("=" * 60)
    print(f"GAP CHECK (flagging gaps > {GAP_THRESHOLD_MINUTES} min)")
    print("=" * 60)
    if df.empty:
        return

    poll_times = sorted(df["polled_at"].unique())
    gaps = []
    for prev, curr in zip(poll_times, poll_times[1:]):
        gap_minutes = (curr - prev) / pd.Timedelta(minutes=1)
        if gap_minutes > GAP_THRESHOLD_MINUTES:
            gaps.append((prev, curr, gap_minutes))

    if not gaps:
        print("No gaps found - ingestion looks continuous.")
        return

    print(f"Found {len(gaps)} gap(s):")
    for prev, curr, gap_minutes in gaps:
        print(f"  {prev} -> {curr}  ({gap_minutes:.0f} min gap)")

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
    df = load_snapshots_df()
    print_overview(df)
    print_per_line_breakdown(df)
    print_gap_report(df)
    print_missing_lines(df)

if __name__ == "__main__":
    main()