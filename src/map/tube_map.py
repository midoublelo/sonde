import folium

LINE_COLOURS = {
    "bakerloo": "#B36305",
    "central": "#E32017",
    "circle": "#FFD300",
    "district": "#00782A",
    "hammersmith-city": "#F3A9BB",
    "jubilee": "#A0A5A9",
    "metropolitan": "#9B0056",
    "northern": "#000000",
    "piccadilly": "#003688",
    "victoria": "#0098D4",
    "waterloo-city": "#95CDBA",
    "elizabeth": "#6950A1",
    "liberty": "#5D6061",
    "lioness": "#FFA600",
    "mildmay": "#0077AD",
    "suffragette": "#5BBD72",
    "weaver": "#823A62",
    "windrush": "#ED1B00",
}

# Status category -> marker colour (matches the timeline's scheme).
STATUS_COLOURS = {
    "Good Service": "#2e7d32",
    "Minor": "#f9a825",
    "Disrupted": "#ef6c00",
    "Suspended": "#c62828",
    "Closed": "#4a148c",
    "Unknown": "#9e9e9e",
}

LONDON_CENTRE = [51.509, -0.128]


def build_map(graph, station_status=None, route_path=None,
              origin_id=None, dest_id=None):
    station_status = station_status or {}
    m = folium.Map(location=LONDON_CENTRE, zoom_start=12, tiles="cartodbpositron")

    for u, v, data in graph.edges(data=True):
        lat_u, lon_u = graph.nodes[u].get("lat"), graph.nodes[u].get("lon")
        lat_v, lon_v = graph.nodes[v].get("lat"), graph.nodes[v].get("lon")
        if None in (lat_u, lon_u, lat_v, lon_v):
            continue
        colour = LINE_COLOURS.get(data["line"], "#888888")
        folium.PolyLine(
            [(lat_u, lon_u), (lat_v, lon_v)],
            color=colour, weight=4, opacity=0.8,
            tooltip=data.get("line_name", data["line"]),
        ).add_to(m)

    # Highlight the route path on top of the network, if given.
    if route_path and len(route_path) > 1:
        coords = [
            (graph.nodes[n]["lat"], graph.nodes[n]["lon"])
            for n in route_path
            if graph.nodes[n].get("lat") is not None
        ]
        folium.PolyLine(
            coords, color="#111111", weight=8, opacity=0.6,
            tooltip="Planned route",
        ).add_to(m)

    for node_id, node in graph.nodes(data=True):
        lat, lon = node.get("lat"), node.get("lon")
        if lat is None or lon is None:
            continue
        # Origin/destination get distinct larger markers.
        if node_id == origin_id:
            folium.Marker(
                (lat, lon), tooltip=f"Start: {node.get('name')}",
                icon=folium.Icon(color="green", icon="play"),
            ).add_to(m)
            continue
        if node_id == dest_id:
            folium.Marker(
                (lat, lon), tooltip=f"Destination: {node.get('name')}",
                icon=folium.Icon(color="red", icon="stop"),
            ).add_to(m)
            continue
        category = station_status.get(node_id, "Unknown")
        colour = STATUS_COLOURS.get(category, STATUS_COLOURS["Unknown"])
        folium.CircleMarker(
            (lat, lon), radius=5, color=colour, fill=True,
            fill_color=colour, fill_opacity=0.9,
            tooltip=node.get("name", node_id),
            popup=folium.Popup(node_id, max_width=200),
        ).add_to(m)

    return m