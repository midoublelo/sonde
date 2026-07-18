from dataclasses import dataclass

import networkx as nx

@dataclass
class RouteLeg:
    """One uninterrupted stretch of travel on a single line."""
    line_name: str
    from_station: str
    to_station: str
    stops: int  # number of stations travelled on this leg

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
            lines.append(
                f"Take the {leg.line_name} line from {leg.from_station} "
                f"to {leg.to_station} ({leg.stops} stop{'s' if leg.stops != 1 else ''})"
            )
        summary = f"{self.total_stops} stops total, {self.interchanges} change(s)"
        return "\n".join(lines) + f"\n\n{summary}"

class StationNotFoundError(Exception):
    pass

def _build_name_index(graph: nx.MultiGraph) -> dict[str, str]:
    """Maps lowercased station name -> station id (graph node key)."""
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

def _cheapest_edge(graph: nx.MultiGraph, u: str, v: str) -> dict:
    edge_data = graph.get_edge_data(u, v)
    return next(iter(edge_data.values()))

def find_route(graph: nx.MultiGraph, origin: str, destination: str) -> Route:
    origin_id = resolve_station(graph, origin)
    dest_id = resolve_station(graph, destination)

    path = nx.shortest_path(graph, origin_id, dest_id)

    legs: list[RouteLeg] = []
    current_line = None
    leg_start_idx = 0

    for i in range(len(path) - 1):
        edge = _cheapest_edge(graph, path[i], path[i + 1])
        line_name = edge["line_name"]

        if current_line is None:
            current_line = line_name
        elif line_name != current_line:
            # Line changed - close out the leg that just ended.
            legs.append(
                RouteLeg(
                    line_name=current_line,
                    from_station=graph.nodes[path[leg_start_idx]]["name"],
                    to_station=graph.nodes[path[i]]["name"],
                    stops=i - leg_start_idx,
                )
            )
            leg_start_idx = i
            current_line = line_name

    # Final leg.
    legs.append(
        RouteLeg(
            line_name=current_line,
            from_station=graph.nodes[path[leg_start_idx]]["name"],
            to_station=graph.nodes[path[-1]]["name"],
            stops=len(path) - 1 - leg_start_idx,
        )
    )

    return Route(legs=legs)