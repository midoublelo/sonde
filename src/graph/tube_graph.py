import networkx as nx

from src.ingestion.tfl_client import get_lines, get_route_sequence

def build_tube_graph() -> nx.MultiGraph:
    graph = nx.MultiGraph()

    for line in get_lines(mode="tube"):
        line_id = line["id"]
        sequence = get_route_sequence(line_id, direction="outbound")

        for stop_point_sequence in sequence.get("stopPointSequences", []):
            stops = stop_point_sequence.get("stopPoint", [])

            for station in stops:
                graph.add_node(
                    station["id"],
                    name=station.get("name", station["id"]),
                    lat=station.get("lat"),
                    lon=station.get("lon"),
                )

            # Consecutive stops in the ordered sequence become edges.
            for a, b in zip(stops, stops[1:]):
                graph.add_edge(a["id"], b["id"], line=line_id, line_name=line["name"])

    return graph

def save_graph(graph: nx.MultiGraph, path: str) -> None:
    import json

    data = nx.node_link_data(graph)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_graph(path: str) -> nx.MultiGraph:
    import json

    with open(path) as f:
        data = json.load(f)
    return nx.node_link_graph(data, multigraph=True)