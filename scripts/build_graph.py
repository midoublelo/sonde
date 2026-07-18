from src.graph.tube_graph import build_tube_graph, save_graph

OUTPUT_PATH = "data/tube_graph.json"

if __name__ == "__main__":
    graph = build_tube_graph()
    save_graph(graph, OUTPUT_PATH)
    print(f"Saved graph with {graph.number_of_nodes()} stations and "
          f"{graph.number_of_edges()} edges to {OUTPUT_PATH}")