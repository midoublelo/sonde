from typing import Callable

import networkx as nx
from sqlalchemy import select

from src.routing.pathfinder import (
    Route,
    StationNotFoundError,
    build_legs,
    resolve_station,
)
from src.storage.models import LineStatusSnapshot

# Higher = more disruptive. "closed"/"suspended" are intentionally high
# rather than infinite: a route through a closed line should still be
# possible to compute (better than crashing) if it's truly the only path,
# it'll just be heavily deprioritized against any alternative.
_STATUS_PENALTIES: dict[str, float] = {
    "good service": 0,
    "special service": 1,
    "minor delays": 2,
    "reduced service": 3,
    "planned closure": 4,
    "part closure": 4,
    "severe delays": 6,
    "part suspended": 8,
    "suspended": 12,
    "closed": 12,
}
_DEFAULT_PENALTY = 3  # unrecognized status text: assume "somewhat disrupted"

def _penalty_for_description(description: str) -> float:
    key = description.strip().lower()
    return _STATUS_PENALTIES.get(key, _DEFAULT_PENALTY)

def get_current_line_status(session) -> dict[str, str]:
    rows = session.execute(select(LineStatusSnapshot).order_by(LineStatusSnapshot.polled_at.desc())).scalars()

    latest: dict[str, str] = {}
    for row in rows:
        if row.line_id not in latest:
            latest[row.line_id] = row.status_description
    return latest

def get_latest_snapshots(session) -> list[LineStatusSnapshot]:
    rows = session.execute(select(LineStatusSnapshot).order_by(LineStatusSnapshot.polled_at.desc())).scalars()

    latest: dict[str, LineStatusSnapshot] = {}
    for row in rows:
        if row.line_id not in latest:
            latest[row.line_id] = row
    return sorted(latest.values(), key=lambda r: r.line_name)

def _make_edge_selector(line_status: dict[str, str]) -> Callable[[nx.MultiGraph, str, str], dict]:
    def selector(graph: nx.MultiGraph, u: str, v: str) -> dict:
        edges = graph.get_edge_data(u, v).values()
        return min(
            edges,
            key=lambda e: _penalty_for_description(
                line_status.get(e["line"], "")
            ),
        )
    return selector

def _make_weight_fn(line_status: dict[str, str]) -> Callable:
    def weight(u, v, edge_dict):
        best = min(
            edge_dict.values(),
            key=lambda e: _penalty_for_description(line_status.get(e["line"], "")),
        )
        penalty = _penalty_for_description(line_status.get(best["line"], ""))
        return 1 + penalty  # base cost of 1 stop, plus disruption penalty
    return weight

def find_route_live(graph: nx.MultiGraph, origin: str, destination: str, session) -> Route:
    origin_id = resolve_station(graph, origin)
    dest_id = resolve_station(graph, destination)

    line_status = get_current_line_status(session)
    selector = _make_edge_selector(line_status)
    weight_fn = _make_weight_fn(line_status)

    path = nx.shortest_path(graph, origin_id, dest_id, weight=weight_fn)
    legs = build_legs(graph, path, edge_selector=selector)

    name_to_description: dict[str, str] = {}
    for _, _, data in graph.edges(data=True):
        if data["line"] in line_status:
            name_to_description[data["line_name"]] = line_status[data["line"]]

    for leg in legs:
        description = name_to_description.get(leg.line_name)
        if description and description.strip().lower() != "good service":
            leg.status_note = description

    return Route(legs=legs)