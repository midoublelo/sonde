import streamlit as st

from src.graph.tube_graph import load_graph
from src.routing.live_routing import find_route_live, get_latest_snapshots
from src.routing.pathfinder import StationNotFoundError, find_route
from src.storage.db import get_session

GRAPH_PATH = "data/tube_graph.json"

st.set_page_config(page_title="sonde", page_icon="\U0001f687", layout="wide")

@st.cache_resource
def get_graph():
    return load_graph(GRAPH_PATH)

def render_live_status():
    st.subheader("Current line status")
    st.caption("Most recent snapshot per line, from the ingestion pipeline.")

    with get_session() as session:
        snapshots = get_latest_snapshots(session)

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
        "Full disruption-cascade *prediction* (how often a delay on one "
        "line historically ripples to others) needs Phase 2 history data "
        "and isn't built yet. What's shown below is groundwork that "
        "doesn't need any of that: which stations are structurally most "
        "critical, based purely on the network's shape. A disruption at "
        "a high-betweenness station is more likely to force reroutes "
        "across the network, regardless of what the data eventually shows."
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

def render_placeholder(title: str, description: str):
    st.subheader(title)
    st.info(f"**Not yet implemented.** {description}")

def main():
    st.title("sonde")

    tabs = st.tabs(
        [
            "Live Status",
            "Journey Planner",
            "Cascade Analysis",
            "Reliability",
            "Anomalies",
            "Footfall",
        ]
    )

    with tabs[0]:
        render_live_status()
    with tabs[1]:
        render_journey_planner()
    with tabs[2]:
        render_cascade_preview()
    with tabs[3]:
        render_placeholder(
            "Reliability",
            "How consistent vs. volatile each line's disruptions are, "
            "beyond just current status.",
        )
    with tabs[4]:
        render_placeholder(
            "Anomaly detection",
            "Flags disruptions that are unusual for a given line and "
            "time, not just any disruption.",
        )
    with tabs[5]:
        render_placeholder(
            "Footfall correlation",
            "Whether busier stations see more delays, using TfL station "
            "usage data.",
        )

if __name__ == "__main__":
    main()