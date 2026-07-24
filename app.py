import json
import os

import streamlit as st
import altair as alt
from streamlit_folium import st_folium

from scripts.build_db import rebuild as rebuild_db_from_logs
from src.graph.tube_graph import load_graph
from src.routing.live_routing import find_route_live, get_latest_snapshots
from src.routing.pathfinder import StationNotFoundError, find_route, estimated_minutes
from src.storage.db import get_session, init_db
from src.storage.models import WeatherSnapshot
from sqlalchemy import select

from src.map.tube_map import build_map

from src.analytics.history import (
    load_status_history,
    load_weather_history,
    reliability_scoreboard,
    status_timeline_categorical,
    weather_disruption_crosstab,
    affected_stations,
    categorize_status
)

GRAPH_PATH = "data/tube_graph.json"
CENTRALITY_PATH = "data/station_centrality.json"

st.set_page_config(page_title="sonde", page_icon="\U0001f687", layout="wide")
init_db() 

@st.cache_data(ttl=300)
def _cached_rebuild():
    return rebuild_db_from_logs()

_cached_rebuild()

@st.cache_resource
def get_graph():
    if not os.path.exists(GRAPH_PATH):
        return None
    return load_graph(GRAPH_PATH)

def render_live_status():
    st.subheader("Current line status")
    st.caption("Most recent snapshot per line, from the ingestion pipeline.")

    with get_session() as session:
        snapshots = get_latest_snapshots(session)
        weather = session.execute(
            select(WeatherSnapshot).order_by(WeatherSnapshot.polled_at.desc())
        ).scalars().first()

    if weather:
        col1, col2, col3 = st.columns(3)
        col1.metric("London weather", weather.weather_description.title())
        col2.metric("Temperature", f"{weather.temp_c:.1f}°C")
        col3.metric("Rain (last hr)", f"{weather.rain_1h_mm or 0:.1f} mm")
        st.divider()

    if not snapshots:
        st.info(
            "No data yet. Once the GitHub Action (or a manual run of "
            "`python -m scripts.run_ingestion`) has completed at least "
            "once, line status will show up here."
        )
        return

    for snap in snapshots:
        good = snap.status_description.strip().lower() == "good service"
        col1, col2, col3 = st.columns([2, 2, 5])
        with col1:
            st.markdown(f"**{snap.line_name}**")
        with col2:
            if good:
                st.markdown(f":green[{snap.status_description}]")
            else:
                st.markdown(f":orange[{snap.status_description}]")
        with col3:
            if snap.reason:
                st.caption(snap.reason)
        st.caption(f"as of {snap.polled_at.strftime('%Y-%m-%d %H:%M UTC')}")
        st.divider()

def render_journey_planner():
    st.subheader("Journey planner")
    st.caption(
        "Fewest-stops routing over the Tube network. Toggle live mode to "
        "route around current disruptions instead."
    )

    col1, col2 = st.columns(2)
    with col1:
        origin = st.text_input("From", placeholder="e.g. Oxford Circus")
    with col2:
        destination = st.text_input("To", placeholder="e.g. King's Cross")

    live = st.toggle(
        "Use live disruption data",
        value=True,
        help="Prefers lines currently running well; falls back to plain "
        "fewest-stops if no ingestion data exists yet.",
    )

    if st.button("Find route", type="primary") and origin and destination:
        graph = get_graph()
        if graph is None:
            st.error(
                f"No network graph found at `{GRAPH_PATH}`. Run "
                "`python -m scripts.build_graph` and commit the result."
            )
            return
        try:
            if live:
                with get_session() as session:
                    route = find_route_live(graph, origin, destination, session)
            else:
                route = find_route(graph, origin, destination)
        except StationNotFoundError as e:
            st.error(str(e))
            return

        for leg in route.legs:
            with st.container(border=True):
                st.markdown(
                    f"**{leg.line_name} line** — {leg.from_station} → "
                    f"{leg.to_station} ({leg.stops} stop{'s' if leg.stops != 1 else ''})"
                )
                if leg.status_note:
                    st.markdown(f":orange[Currently: {leg.status_note}]")

        st.caption(f"{route.total_stops} stops total, {route.interchanges} change(s)")

def render_cascade_preview():
    st.subheader("Cascade analysis")

    if not os.path.exists(CENTRALITY_PATH):
        st.info(
            "**Coming in Phase 2.** Run `python -m scripts.analyze_network` "
            "to generate a structural preview in the meantime."
        )
        return

    with open(CENTRALITY_PATH) as f:
        centrality = json.load(f)

    st.caption(
        "Structural analysis of the Tube network graph. Betweenness "
        "measures % of shortest paths pass through a station, so high "
        "betweenness stations are critical for network connectivity."
    )

    ranked = sorted(
        centrality.values(), key=lambda r: r["betweenness"], reverse=True
    )[:15]

    st.dataframe(
        [
            {
                "Station": r["name"],
                "Betweenness": r["betweenness"],
                "Lines through station": r["line_count"],
            }
            for r in ranked
        ],
        hide_index=True,
        width="stretch",
    )

def render_reliability():
    st.subheader("Reliability scoreboard")
    st.caption(
        "Descriptive stats over the data collected."
    )

    status_df = load_status_history()
    if status_df.empty:
        st.info("No status history yet.")
        return

    board = reliability_scoreboard(status_df)
    st.dataframe(board, hide_index=True, width="stretch")

    span = status_df["polled_at"].max() - status_df["polled_at"].min()
    st.caption(
        f"Based on {len(status_df)} snapshots spanning {span}. "
        "Disruption episodes count consecutive bad polls as one event."
    )

def render_timeline():
    st.subheader("Status timeline")
    st.caption(
        "Each line's status category over time. Categorized from TfL's own "
        "status descriptions"
    )

    status_df = load_status_history()
    if status_df.empty:
        st.info("No status history yet.")
        return

    timeline = status_timeline_categorical(status_df)

    # Fixed color mapping so "good" always reads green, "closed" always red,
    # regardless of what's present in the current data window.
    color_scale = alt.Scale(
        domain=["Good Service", "Minor", "Disrupted", "Suspended", "Closed"],
        range=["#2e7d32", "#f9a825", "#ef6c00", "#c62828", "#4a148c"],
    )

    chart = (
        alt.Chart(timeline)
        .mark_circle(size=60)
        .encode(
            x=alt.X("polled_at:T", title="Time"),
            y=alt.Y("line_name:N", title="Line"),
            color=alt.Color("category:N", scale=color_scale, title="Status"),
            tooltip=["polled_at:T", "line_name:N", "category:N"],
        )
        .properties(height=400)
    )
    st.altair_chart(chart, use_container_width=True)

    weather_df = load_weather_history()
    if not weather_df.empty:
        st.caption("Temperature over the same period:")
        st.line_chart(weather_df.set_index("polled_at")["temp_c"])

def render_weather_crosstab():
    st.subheader("Weather vs. disruption")
    st.caption(
        "For each weather condition, the share of line-status observations "
        "that were disrupted."
    )

    status_df = load_status_history()
    weather_df = load_weather_history()
    crosstab = weather_disruption_crosstab(status_df, weather_df)

    if crosstab.empty:
        st.info("Not enough overlapping status + weather data yet.")
        return

    st.dataframe(crosstab, hide_index=True, width="stretch")
    total_obs = crosstab["Observations"].sum()
    st.caption(
        f"Based on {total_obs} status observations matched to weather "
        "within 30 minutes. Small counts = treat with caution."
    )

def render_affected_stations():
    st.subheader("Affected stations")
    st.caption(
        "Stations touched by a disrupted line, by number of affected polls. "
    )

    status_df = load_status_history()
    graph = get_graph()
    if graph is None:
        st.error("No network graph found - run scripts.build_graph.")
        return

    affected = affected_stations(status_df, graph)
    if affected.empty:
        st.info("No disruptions observed yet - nothing to show.")
        return

    st.dataframe(
        affected[["name", "affected_polls"]].head(25),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        f"{len(affected)} stations affected across the data so far. "
        "(lat/lon are included in the data for the map view - not shown here.)"
    )

def _current_station_status(graph, status_df):
    if status_df.empty:
        return {}

    # Latest status category per line_id.
    latest = (
        status_df.sort_values("polled_at")
        .groupby("line_id")
        .last()
        .reset_index()
    )
    line_category = {
        row["line_id"]: categorize_status(row["status_description"])
        for _, row in latest.iterrows()
    }

    # Severity ordering so we can pick the "worst" per station.
    order = {c: i for i, c in enumerate(
        ["Good Service", "Minor", "Disrupted", "Suspended", "Closed"]
    )}

    station_cat = {}
    for u, v, data in graph.edges(data=True):
        cat = line_category.get(data["line"])
        if cat is None:
            continue
        for node in (u, v):
            existing = station_cat.get(node)
            if existing is None or order.get(cat, 0) > order.get(existing, 0):
                station_cat[node] = cat
    return station_cat

def _station_lines(graph, station_id):
    """All (line_id, line_name) pairs serving a station."""
    lines = {}
    for u, v, data in graph.edges(data=True):
        if station_id in (u, v):
            lines[data["line"]] = data.get("line_name", data["line"])
    return lines


def render_station_detail(graph, status_df, station_id):
    node = graph.nodes.get(station_id)
    if node is None:
        st.info("Click a station on the map to see its details and plan a journey.")
        return

    station_name = node.get("name", station_id)
    st.markdown(f"### {station_name}")

    # --- Journey planning buttons ---
    st.markdown("**Plan a journey:**")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🟢 Set as start", key="set_start"):
            st.session_state["journey_origin"] = station_id
            st.rerun()
    with col2:
        if st.button("🔴 Set as destination", key="set_dest"):
            st.session_state["journey_dest"] = station_id
            st.rerun()

    origin_id = st.session_state.get("journey_origin")
    dest_id = st.session_state.get("journey_dest")

    # Show current selection + clear option
    if origin_id or dest_id:
        o_name = graph.nodes[origin_id]["name"] if origin_id else "—"
        d_name = graph.nodes[dest_id]["name"] if dest_id else "—"
        st.caption(f"From: {o_name}  →  To: {d_name}")
        if st.button("Clear journey", key="clear_journey"):
            st.session_state.pop("journey_origin", None)
            st.session_state.pop("journey_dest", None)
            st.rerun()

    st.divider()

    # --- Current status of serving lines (unchanged) ---
    lines = _station_lines(graph, station_id)
    st.markdown("**Lines serving this station — current status:**")
    if status_df.empty:
        st.caption("No status data yet.")
    else:
        latest = status_df.sort_values("polled_at").groupby("line_id").last()
        for line_id, line_name in sorted(lines.items(), key=lambda x: x[1]):
            if line_id in latest.index:
                desc = latest.loc[line_id, "status_description"]
                cat = categorize_status(desc)
                colour = ":green" if cat == "Good Service" else ":orange"
                st.markdown(f"- {line_name}: {colour}[{desc}]")
            else:
                st.markdown(f"- {line_name}: _no data_")

    # --- Historical reliability (unchanged) ---
    st.markdown("**Historical reliability (data so far):**")
    if not status_df.empty:
        board = reliability_scoreboard(status_df)
        sub = board[board["Line"].isin(set(lines.values()))]
        if not sub.empty:
            st.dataframe(sub, hide_index=True, width="stretch")
        else:
            st.caption("No history for these lines yet.")

def render_map_view():
    graph = get_graph()
    if graph is None:
        st.error("No network graph found — run scripts.build_graph.")
        return

    status_df = load_status_history()
    station_status = _current_station_status(graph, status_df)

    origin_id = st.session_state.get("journey_origin")
    dest_id = st.session_state.get("journey_dest")

    # Compute route if both ends are set.
    route, route_path = None, None
    if origin_id and dest_id:
        from src.routing.pathfinder import find_route_by_ids
        try:
            route, route_path = find_route_by_ids(graph, origin_id, dest_id)
        except Exception as e:
            st.warning(f"Couldn't compute route: {e}")

    map_col, detail_col = st.columns([3, 2])

    with map_col:
        fmap = build_map(graph, station_status, route_path, origin_id, dest_id)
        map_state = st_folium(
            fmap, width=None, height=600,
            returned_objects=["last_object_clicked_popup"],
        )
        # Show route summary under the map.
        if route:
            st.markdown("**Planned route:**")
            for leg in route.legs:
                note = f" — :orange[{leg.status_note}]" if leg.status_note else ""
                st.markdown(
                    f"- {leg.line_name}: {leg.from_station} → "
                    f"{leg.to_station} ({leg.stops} stops){note}"
                )
            mins = estimated_minutes(route)
            st.caption(
                f"{route.total_stops} stops, {route.interchanges} change(s) · "
                f"~{mins:.0f} min (estimated)"
            )
    clicked = map_state.get("last_object_clicked_popup") if map_state else None
    if clicked and clicked != st.session_state.get("_last_clicked"):
        st.session_state["selected_station"] = clicked
        st.session_state["_last_clicked"] = clicked

    with detail_col:
        render_station_detail(graph, status_df,
                              st.session_state.get("selected_station"))

def render_placeholder(title: str, description: str):
    st.subheader(title)
    st.info(f"**Not yet implemented.** {description}")

def render_sidebar(graph, status_df):
    with st.sidebar:
        st.markdown("### Journey")
        origin_id = st.session_state.get("journey_origin")
        dest_id = st.session_state.get("journey_dest")

        if origin_id or dest_id:
            o = graph.nodes[origin_id]["name"] if origin_id else "—"
            d = graph.nodes[dest_id]["name"] if dest_id else "—"
            st.markdown(f"**From:** {o}")
            st.markdown(f"**To:** {d}")
            if st.button("Clear journey", width="stretch"):
                st.session_state.pop("journey_origin", None)
                st.session_state.pop("journey_dest", None)
                st.rerun()
        else:
            st.caption(
                "Click a station on the map, then set it as your start "
                "or destination."
            )

        st.divider()

        # --- Network status summary ---
        st.markdown("### Network status")
        if status_df.empty:
            st.caption("No status data yet.")
        else:
            latest = status_df.sort_values("polled_at").groupby("line_id").last()
            categories = {
                line_id: categorize_status(row["status_description"])
                for line_id, row in latest.iterrows()
            }
            good = [l for l, c in categories.items() if c == "Good Service"]
            bad = {l: c for l, c in categories.items() if c != "Good Service"}

            st.metric("Lines running normally", f"{len(good)} / {len(categories)}")
            if bad:
                for line_id, cat in sorted(bad.items()):
                    name = latest.loc[line_id, "line_name"]
                    reason = latest.loc[line_id, "reason"]
                    with st.expander(f"{name} — {cat}"):
                        if reason and str(reason).strip() and str(reason) != "nan":
                            st.caption(reason)
                        else:
                            st.caption("No reason given by TfL.")

        st.divider()

        # --- Data freshness ---
        st.markdown("### Data")
        if status_df.empty:
            st.caption("No data ingested yet.")
        else:
            last_poll = status_df["polled_at"].max()
            span = status_df["polled_at"].max() - status_df["polled_at"].min()
            st.caption(f"Last poll: {last_poll.strftime('%Y-%m-%d %H:%M UTC')}")
            st.caption(f"Records: {len(status_df)} over {span}")

        if st.button("🔄 Force refresh", width="stretch"):
            _cached_rebuild.clear()
            tube_count, weather_count = _cached_rebuild()
            st.success(f"Rebuilt: {tube_count} Tube, {weather_count} weather")

def main():
    st.title("\U0001f687 sonde")

    graph = get_graph()
    status_df = load_status_history()

    if graph is not None:
        render_sidebar(graph, status_df)

    render_map_view()

    st.divider()

    tabs = st.tabs(
        [
            "Live Status",
            "Cascade Analysis",
            "Reliability",
            "Anomalies",
            "Footfall",
        ]
    )

    with tabs[0]:
        render_live_status()
        render_timeline()
    with tabs[1]:
        render_cascade_preview()
    with tabs[2]:
        render_reliability()
        render_weather_crosstab()
        render_affected_stations()
    with tabs[3]:
        render_placeholder(
            "Anomaly detection",
            "Flags disruptions that are unusual for a given line and "
            "time, not just any disruption.",
        )
    with tabs[4]:
        render_placeholder(
            "Footfall correlation",
            "Whether busier stations see more delays, using TfL station "
            "usage data.",
        )

if __name__ == "__main__":
    main()