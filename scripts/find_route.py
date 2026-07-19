import sys

from src.graph.tube_graph import load_graph
from src.routing.pathfinder import StationNotFoundError, find_route
from src.storage.db import get_session

GRAPH_PATH = "data/tube_graph.json"

def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--live"]
    live = "--live" in sys.argv

    if len(args) != 2:
        print('Usage: python -m scripts.find_route "<origin>" "<destination>" [--live]')
        sys.exit(1)

    origin, destination = args
    graph = load_graph(GRAPH_PATH)

    try:
        if live:
            from src.routing.live_routing import find_route_live

            with get_session() as session:
                route = find_route_live(graph, origin, destination, session)
        else:
            route = find_route(graph, origin, destination)
    except StationNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(route.describe())

if __name__ == "__main__":
    main()