import json
 
import networkx as nx
 
from src.graph.tube_graph import load_graph
 
GRAPH_PATH = "data/tube_graph.json"
OUTPUT_PATH = "data/station_centrality.json"
TOP_N = 15
 
 
def compute_line_counts(graph: nx.MultiGraph) -> dict[str, int]:
    """Number of distinct lines physically passing through each station."""
    lines_per_station: dict[str, set] = {node: set() for node in graph.nodes}
    for u, v, data in graph.edges(data=True):
        lines_per_station[u].add(data["line"])
        lines_per_station[v].add(data["line"])
    return {node: len(lines) for node, lines in lines_per_station.items()}
 
 
def compute_centrality(graph: nx.MultiGraph) -> dict[str, dict]:
    betweenness = nx.betweenness_centrality(graph)
    degree = nx.degree_centrality(graph)
    closeness = nx.closeness_centrality(graph)
    line_counts = compute_line_counts(graph)
 
    results = {}
    for node in graph.nodes:
        results[node] = {
            "name": graph.nodes[node].get("name", node),
            "betweenness": round(betweenness[node], 4),
            "degree": round(degree[node], 4),
            "closeness": round(closeness[node], 4),
            "line_count": line_counts[node],
        }
    return results
 
 
def print_top_stations(results: dict[str, dict], by: str, n: int = TOP_N) -> None:
    ranked = sorted(results.values(), key=lambda r: r[by], reverse=True)[:n]
    print(f"\nTop {n} stations by {by}:")
    for i, station in enumerate(ranked, start=1):
        value = station[by]
        value_str = str(value) if by == "line_count" else f"{value:.4f}"
        print(
            f"  {i:2d}. {station['name']:35s} {by}={value_str}  "
            f"({station['line_count']} lines)"
        )
 
 
def main() -> None:
    graph = load_graph(GRAPH_PATH)
    results = compute_centrality(graph)
 
    print_top_stations(results, "betweenness")
    print_top_stations(results, "line_count")
 
    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull results for all {len(results)} stations saved to {OUTPUT_PATH}")
 
 
if __name__ == "__main__":
    main()