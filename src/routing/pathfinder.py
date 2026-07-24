from dataclasses import dataclass
from typing import Callable

import networkx as nx

@dataclass
class RouteLeg:
    line_name: str
    from_station: str
    to_station: str
    stops: int  # number of stations travelled on this leg
    status_note: str | None = None  # e.g. "Severe Delays" - set by live-aware routing

@dataclass
class Route:
    legs: list[RouteLeg]

    @property
    def total_stops(self) -> int:
        return sum(leg.stops for leg in self.legs)

    @property
    def interchanges(self) -> int:
        return max(len(self.legs) - 1, 0)

    def describe(self) -> str:
        lines = []
        for leg in self.legs:
            note = f" - currently: {leg.status_note}" if leg.status_note else ""
            lines.append(
                f"Take the {leg.line_name} line from {leg.from_station} "
                f"to {leg.to_station} ({leg.stops} stop{'s' if leg.stops != 1 else ''}){note}"
            )
        summary = f"{self.total_stops} stops total, {self.interchanges} change(s)"
        return "\n".join(lines) + f"\n\n{summary}"

class StationNotFoundError(Exception):
    pass

def _build_name_index(graph: nx.MultiGraph) -> dict[str, str]:
    return {
        data["name"].lower(): node_id
        for node_id, data in graph.nodes(data=True)
        if "name" in data
    }

def resolve_station(graph: nx.MultiGraph, query: str) -> str:
    index = _build_name_index(graph)
    query_lower = query.strip().lower()

    if query_lower in index:
        return index[query_lower]

    matches = {name: node_id for name, node_id in index.items() if query_lower in name}
    if len(matches) == 1:
        return next(iter(matches.values()))
    if len(matches) > 1:
        options = ", ".join(sorted(matches)[:5])
        raise StationNotFoundError(
            f"'{query}' is ambiguous - matched multiple stations: {options}. "
            "Try being more specific."
        )
    raise StationNotFoundError(f"No station found matching '{query}'.")

def _first_edge(graph: nx.MultiGraph, u: str, v: str) -> dict:
    edge_data = graph.get_edge_data(u, v)
    return next(iter(edge_data.values()))

def build_legs(
    graph: nx.MultiGraph,
    path: list[str],
    edge_selector: Callable[[nx.MultiGraph, str, str], dict] = _first_edge,
    status_lookup: Callable[[str], str | None] | None = None,
) -> list[RouteLeg]:
    legs: list[RouteLeg] = []
    current_line = None
    leg_start_idx = 0

    for i in range(len(path) - 1):
        edge = edge_selector(graph, path[i], path[i + 1])
        line_name = edge["line_name"]

        if current_line is None:
            current_line = line_name
        elif line_name != current_line:
            legs.append(
                RouteLeg(
                    line_name=current_line,
                    from_station=graph.nodes[path[leg_start_idx]]["name"],
                    to_station=graph.nodes[path[i]]["name"],
                    stops=i - leg_start_idx,
                    status_note=status_lookup(current_line) if status_lookup else None,
                )
            )
            leg_start_idx = i
            current_line = line_name

    legs.append(
        RouteLeg(
            line_name=current_line,
            from_station=graph.nodes[path[leg_start_idx]]["name"],
            to_station=graph.nodes[path[-1]]["name"],
            stops=len(path) - 1 - leg_start_idx,
            status_note=status_lookup(current_line) if status_lookup else None,
        )
    )
    return legs

def find_route(graph: nx.MultiGraph, origin: str, destination: str) -> Route:
    origin_id = resolve_station(graph, origin)
    dest_id = resolve_station(graph, destination)

    path = nx.shortest_path(graph, origin_id, dest_id)
    return Route(legs=build_legs(graph, path))

def find_route_by_ids(graph, origin_id, destination_id):
    path = nx.shortest_path(graph, origin_id, destination_id)
    return Route(legs=build_legs(graph, path)), path

_MINUTES_PER_STOP = 2.0
_MINUTES_PER_INTERCHANGE = 5.0

def estimated_minutes(self) -> float:
    """
    Rough journey-time estimate from structure alone: stops x avg
    run-time, plus an interchange penalty for each line change.
    This is an APPROXIMATION - real times vary by line, time of day,
    and current disruptions, none of which this accounts for.
    """
    return (
        self.total_stops * _MINUTES_PER_STOP
        + self.interchanges * _MINUTES_PER_INTERCHANGE
    )