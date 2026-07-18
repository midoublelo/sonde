import sys

from src.graph.tube_graph import load_graph
from src.routing.pathfinder import StationNotFoundError, find_route

GRAPH_PATH = "data/tube_graph.json"

def main() -> None:
    if len(sys.argv) != 3:
        print('Usage: python -m scripts.find_route "<origin>" "<destination>"')
        sys.exit(1)

    origin, destination = sys.argv[1], sys.argv[2]
    graph = load_graph(GRAPH_PATH)

    try:
        route = find_route(graph, origin, destination)
    except StationNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(route.describe())

if __name__ == "__main__":
    main()