import sys

from src.graph.tube_graph import load_graph
from src.routing.pathfinder import StationNotFoundError, find_route
from src.storage.db import get_session

GRAPH_PATH = "data/tube_graph.json"

USAGE = (
    'Usage:\n'
    '  python -m scripts.find_route "<origin>" "<destination>"\n'
    '  python -m scripts.find_route "<origin>" "<destination>" --live\n'
    '  python -m scripts.find_route "<origin>" "<destination>" --reliable HH [--weekend]\n'
    '\n'
    '  --live       route around lines disrupted right now\n'
    '  --reliable HH  route around lines historically unreliable at local hour HH\n'
    '  --weekend    with --reliable, predict for a weekend instead of a weekday'
)

def main() -> None:
    argv = sys.argv[1:]
    live = "--live" in argv
    reliable = "--reliable" in argv
    weekend = "--weekend" in argv

    rel_hour = None
    if reliable:
        i = argv.index("--reliable")
        try:
            rel_hour = int(argv[i + 1])
            del argv[i:i + 2]
        except (IndexError, ValueError):
            print("--reliable needs an hour 0-23, e.g. --reliable 18")
            sys.exit(1)

    positional = [a for a in argv if not a.startswith("--")]
    if len(positional) != 2:
        print(USAGE)
        sys.exit(1)

    origin, destination = positional
    graph = load_graph(GRAPH_PATH)

    try:
        if reliable:
            from src.analytics.baseline_model import fit_model
            from src.analytics.history import load_status_history
            from src.routing.reliability_routing import find_route_reliable

            model = fit_model(load_status_history())
            if model is None or not model.line_names:
                print("No history available to build the reliability model.")
                sys.exit(1)
            route = find_route_reliable(
                graph, origin, destination, model, rel_hour, weekend
            )
        elif live:
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
