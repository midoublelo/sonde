from __future__ import annotations

from typing import Callable

import networkx as nx

from src.analytics.baseline_model import DisruptionRateModel
from src.routing.pathfinder import Route, build_legs, resolve_station

RELIABILITY_WEIGHT = 6.0

def _make_weight_fn(
    model: DisruptionRateModel, hour: int, is_weekend: bool
) -> Callable:

    def weight(u, v, edge_dict):
        best = min(
            edge_dict.values(),
            key=lambda e: model.predict(e["line"], hour, is_weekend),
        )
        prob = model.predict(best["line"], hour, is_weekend)
        return 1.0 + prob * RELIABILITY_WEIGHT

    return weight

def _make_edge_selector(
    model: DisruptionRateModel, hour: int, is_weekend: bool
) -> Callable[[nx.MultiGraph, str, str], dict]:
    """Pick the most historically-reliable parallel line for narration."""

    def selector(graph: nx.MultiGraph, u: str, v: str) -> dict:
        edges = graph.get_edge_data(u, v).values()
        return min(edges, key=lambda e: model.predict(e["line"], hour, is_weekend))

    return selector

def find_route_reliable(
    graph: nx.MultiGraph,
    origin: str,
    destination: str,
    model: DisruptionRateModel,
    hour: int,
    is_weekend: bool,
) -> Route:
    origin_id = resolve_station(graph, origin)
    dest_id = resolve_station(graph, destination)
    return _route_between_ids(graph, origin_id, dest_id, model, hour, is_weekend)

def find_route_reliable_by_ids(
    graph: nx.MultiGraph,
    origin_id: str,
    destination_id: str,
    model: DisruptionRateModel,
    hour: int,
    is_weekend: bool,
) -> tuple[Route, list[str]]:
    route = _route_between_ids(
        graph, origin_id, destination_id, model, hour, is_weekend
    )
    path = nx.shortest_path(
        graph,
        origin_id,
        destination_id,
        weight=_make_weight_fn(model, hour, is_weekend),
    )
    return route, path

def _route_between_ids(
    graph: nx.MultiGraph,
    origin_id: str,
    dest_id: str,
    model: DisruptionRateModel,
    hour: int,
    is_weekend: bool,
) -> Route:
    weight_fn = _make_weight_fn(model, hour, is_weekend)
    selector = _make_edge_selector(model, hour, is_weekend)

    path = nx.shortest_path(graph, origin_id, dest_id, weight=weight_fn)
    legs = build_legs(graph, path, edge_selector=selector)

    name_to_id: dict[str, str] = {}
    for _, _, data in graph.edges(data=True):
        name_to_id.setdefault(data["line_name"], data["line"])

    for leg in legs:
        line_id = name_to_id.get(leg.line_name)
        if line_id is not None:
            pct = model.predict_rate(line_id, hour, is_weekend)
            leg.status_note = f"~{pct:.0f}% historically disrupted at this time"

    return Route(legs=legs)