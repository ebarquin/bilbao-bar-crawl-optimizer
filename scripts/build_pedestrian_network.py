#!/usr/bin/env python3
"""Build a cached OSM pedestrian graph and assign venues to graph nodes."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import networkx as nx
import osmnx as ox
from pyproj import Transformer
from shapely.geometry import LineString, mapping, shape
from shapely.ops import transform
from shapely.geometry import Point
from shapely.strtree import STRtree


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AREA = ROOT / "data/study-areas/casco-viejo-bilbao.geojson"
DEFAULT_VENUES = ROOT / "data/processed/venues.geojson"
DEFAULT_OVERRIDES = ROOT / "data/study-areas/access-overrides.json"
OUTPUT_DIR = ROOT / "data/processed"
GRAPH_PATH = OUTPUT_DIR / "pedestrian-network.graphml"
ACCESS_PATH = OUTPUT_DIR / "venue-access.json"
REPORT_PATH = OUTPUT_DIR / "pedestrian-network-report.json"
ROUTES_PATH = OUTPUT_DIR / "sample-routes.geojson"
RAW_OSM_PATH = ROOT / "data/raw/pedestrian-network.osm"
MARGIN_METERS = 400
DEFAULT_OVERPASS_URL = "https://overpass.private.coffee/api"
OSM_MAP_URL = "https://api.openstreetmap.org/api/0.6/map"


def read_polygon(path: Path):
    collection = json.loads(path.read_text(encoding="utf-8"))
    geometries = [shape(feature["geometry"]) for feature in collection["features"]]
    if len(geometries) != 1 or geometries[0].geom_type != "Polygon":
        raise ValueError("Study area must contain exactly one Polygon feature")
    return geometries[0]


def buffered_wgs84(polygon, margin_meters: int):
    forward = Transformer.from_crs("EPSG:4326", "EPSG:25830", always_xy=True).transform
    inverse = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True).transform
    return transform(inverse, transform(forward, polygon).buffer(margin_meters))


def edge_geometry(graph: nx.MultiDiGraph, u, v, data: dict):
    geometry = data.get("geometry")
    if geometry is not None:
        return geometry
    return LineString([(graph.nodes[u]["x"], graph.nodes[u]["y"]), (graph.nodes[v]["x"], graph.nodes[v]["y"])])


def bbox_from_polygon(polygon) -> tuple[float, float, float, float]:
    min_x, min_y, max_x, max_y = polygon.bounds
    return min_x, min_y, max_x, max_y


def download_osm_map(polygon, output: Path) -> None:
    west, south, east, north = bbox_from_polygon(polygon)
    url = f"{OSM_MAP_URL}?bbox={west:.7f},{south:.7f},{east:.7f},{north:.7f}"
    request = Request(url, headers={"User-Agent": "BilbaoBarCrawlOptimizer/0.1 (research project)"})
    with urlopen(request, timeout=240) as response:
        output.write_bytes(response.read())
    print(f"Saved OSM map extract: {output}")


def walking_subgraph(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    allowed = {
        "bridleway", "corridor", "cycleway", "footway", "living_street", "path",
        "pedestrian", "primary", "residential", "secondary", "service", "steps",
        "tertiary", "track", "unclassified", "crossing", "sidewalk",
    }
    filtered = graph.copy()
    remove_edges = []
    for u, v, key, data in filtered.edges(keys=True, data=True):
        highway = data.get("highway", [])
        values = set(highway if isinstance(highway, list) else [highway])
        access = set(str(data.get(tag, "")).lower() for tag in ("access", "foot"))
        if not values.intersection(allowed) or "no" in access or "private" in access:
            remove_edges.append((u, v, key))
    filtered.remove_edges_from(remove_edges)
    filtered.remove_nodes_from(list(nx.isolates(filtered)))
    return filtered


def nearest_node_local(graph: nx.MultiDiGraph, lon: float, lat: float):
    """Find the nearest node without optional spatial-index dependencies."""
    return min(
        graph.nodes,
        key=lambda node: (graph.nodes[node]["x"] - lon) ** 2 + (graph.nodes[node]["y"] - lat) ** 2,
    )


def build_edge_index(graph: nx.MultiDiGraph):
    geometries = []
    records = []
    for u, v, key, data in graph.edges(keys=True, data=True):
        geometries.append(edge_geometry(graph, u, v, data))
        records.append((u, v, key))
    return STRtree(geometries), geometries, records


def nearest_street_access(tree, geometries, records, graph, lon: float, lat: float):
    point = Point(lon, lat)
    index = int(tree.nearest(point))
    street = geometries[index]
    snapped = street.interpolate(street.project(point))
    u, v, _key = records[index]
    node = min((u, v), key=lambda candidate: (graph.nodes[candidate]["x"] - lon) ** 2 + (graph.nodes[candidate]["y"] - lat) ** 2)
    return node, [float(snapped.x), float(snapped.y)]


def route_feature(graph, route_id: str, origin_id: str, destination_id: str, path: list):
    features = []
    for index, (u, v) in enumerate(zip(path, path[1:])):
        edge_bundle = graph.get_edge_data(u, v)
        if not edge_bundle:
            continue
        key, data = min(edge_bundle.items(), key=lambda item: item[1].get("length", float("inf")))
        geometry = edge_geometry(graph, u, v, data)
        features.append({
            "type": "Feature",
            "properties": {
                "route_id": route_id,
                "origin": origin_id,
                "destination": destination_id,
                "edge_index": index,
                "osm_edge_key": key,
                "length_m": data.get("length"),
            },
            "geometry": mapping(geometry),
        })
    return features


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--area", type=Path, default=DEFAULT_AREA)
    parser.add_argument("--venues", type=Path, default=DEFAULT_VENUES)
    parser.add_argument("--access-overrides", type=Path, default=DEFAULT_OVERRIDES)
    parser.add_argument("--margin-m", type=int, default=MARGIN_METERS)
    parser.add_argument("--overpass-url", default=DEFAULT_OVERPASS_URL)
    parser.add_argument("--source", choices=("osm-map", "overpass"), default="osm-map")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if GRAPH_PATH.exists() and not args.force:
        print(f"Using cached graph: {GRAPH_PATH}")
        graph = ox.load_graphml(GRAPH_PATH)
    else:
        polygon = read_polygon(args.area)
        network_polygon = buffered_wgs84(polygon, args.margin_m)
        if args.source == "osm-map":
            if not RAW_OSM_PATH.exists() or args.force:
                download_osm_map(network_polygon, RAW_OSM_PATH)
            graph = ox.graph_from_xml(RAW_OSM_PATH, bidirectional=True, simplify=True, retain_all=True)
            graph = walking_subgraph(graph)
        else:
            ox.settings.use_cache = True
            ox.settings.log_console = False
            ox.settings.requests_timeout = 300
            ox.settings.overpass_url = args.overpass_url
            graph = ox.graph_from_polygon(
                network_polygon,
                network_type="walk",
                simplify=True,
                retain_all=True,
                truncate_by_edge=True,
            )
        ox.save_graphml(graph, GRAPH_PATH)
        print(f"Saved pedestrian graph: {GRAPH_PATH}")

    venues = json.loads(args.venues.read_text(encoding="utf-8"))["features"]
    overrides = json.loads(args.access_overrides.read_text(encoding="utf-8")) if args.access_overrides.exists() else {}
    edge_tree, edge_geometries, edge_records = build_edge_index(graph)
    access = []
    for feature in venues:
        lon, lat = feature["geometry"]["coordinates"]
        override = overrides.get(feature["id"])
        street_node, street_point = nearest_street_access(edge_tree, edge_geometries, edge_records, graph, lon, lat)
        node = int(override["node"]) if override else int(street_node)
        access_item = {
            "venue_id": feature["id"],
            "osm_type": feature["properties"]["osm_type"],
            "osm_id": feature["properties"]["osm_id"],
            "name": feature["properties"]["name"],
            "node": int(node),
            "access_method": "manual_override" if override else "nearest_graph_node_from_osm_center",
            "source_point": [lon, lat],
            "graph_point": [graph.nodes[node]["x"], graph.nodes[node]["y"]],
            "street_point": street_point,
        }
        if override:
            access_item["street_name"] = override["street_name"]
            access_item["override_reason"] = override["reason"]
        access.append(access_item)
    ACCESS_PATH.write_text(json.dumps(access, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    weak_components = list(nx.weakly_connected_components(graph))
    component_by_node = {node: index for index, component in enumerate(weak_components) for node in component}
    venue_components = Counter(component_by_node[item["node"]] for item in access)
    largest_component = max(venue_components, key=venue_components.get) if venue_components else None
    outside_largest = [item["venue_id"] for item in access if component_by_node[item["node"]] != largest_component]

    ordered = sorted(access, key=lambda item: item["venue_id"])
    route_features = []
    test_pairs = list(zip(ordered[:3], ordered[1:4]))
    fermin = next((item for item in access if item["venue_id"] == "node/2852257119"), None)
    if fermin:
        comparison = next(item for item in ordered if item["venue_id"] != fermin["venue_id"])
        test_pairs.append((fermin, comparison))
    route_failures = []
    route_results = []
    for index, (origin, destination) in enumerate(test_pairs, start=1):
        route_id = f"sample-{index}"
        try:
            path = nx.shortest_path(graph, origin["node"], destination["node"], weight="length")
            route_features.extend(route_feature(graph, route_id, origin["venue_id"], destination["venue_id"], path))
            route_length = sum(
                min(data.values(), key=lambda item: item.get("length", float("inf"))).get("length", 0)
                for u, v in zip(path, path[1:])
                for data in [graph.get_edge_data(u, v)]
            )
            route_results.append({
                "route_id": route_id,
                "origin": origin["venue_id"],
                "destination": destination["venue_id"],
                "length_m": round(route_length, 2),
                "nodes": len(path),
            })
        except nx.NetworkXNoPath:
            route_failures.append({"route_id": route_id, "origin": origin["venue_id"], "destination": destination["venue_id"], "reason": "no directed path"})

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "study_area": str(args.area.relative_to(ROOT)),
        "graph_file": str(GRAPH_PATH.relative_to(ROOT)),
        "network_type": "walk",
        "source": args.source,
        "directed_graph": graph.is_directed(),
        "margin_meters": args.margin_m,
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "weakly_connected_components": len(weak_components),
        "venue_count": len(access),
        "manual_access_overrides": [item["venue_id"] for item in access if item["access_method"] == "manual_override"],
        "venues_outside_largest_weak_component": outside_largest,
        "route_tests": len(test_pairs),
        "route_results": route_results,
        "route_failures": route_failures,
        "limitations": [
            "Venue points for ways/relations use OSM centers; access nodes are nearest-node proxies.",
            "A successful graph path confirms network connectivity, not physical entrance accuracy.",
            "OSM pedestrian tags may be incomplete or stale and require manual review.",
        ],
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"nodes": report["nodes"], "edges": report["edges"], "venues": len(access), "components": report["weakly_connected_components"], "route_failures": len(route_failures)}))


if __name__ == "__main__":
    main()
