#!/usr/bin/env python3
"""Create one distinct graph node per venue on its nearest pedestrian edge."""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import osmnx as ox
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree


ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = ROOT / "data/processed/pedestrian-network.graphml"
ACCESS_PATH = ROOT / "data/processed/venue-access.json"
REPORT_PATH = ROOT / "data/processed/pedestrian-network-report.json"


def edge_geometry(graph, u, v, data):
    geometry = data.get("geometry")
    if geometry is not None:
        return geometry
    return LineString([(graph.nodes[u]["x"], graph.nodes[u]["y"]), (graph.nodes[v]["x"], graph.nodes[v]["y"])])


def main() -> None:
    graph = ox.load_graphml(GRAPH_PATH)
    if any(data.get("venue_access") == "virtual" for _, data in graph.nodes(data=True)):
        print("Graph already contains virtual venue nodes; nothing to do")
        return
    access = json.loads(ACCESS_PATH.read_text(encoding="utf-8"))
    geometries = []
    records = []
    for u, v, key, data in graph.edges(keys=True, data=True):
        geometries.append(edge_geometry(graph, u, v, data))
        records.append((u, v, key, data))
    tree = STRtree(geometries)
    next_node = max(int(node) for node in graph.nodes) + 1
    physical_groups = {}
    new_access = []

    for item in access:
        point = Point(item["street_point"])
        index = int(tree.nearest(point))
        u, v, key, data = records[index]
        geometry = geometries[index]
        ratio = geometry.project(point) / geometry.length if geometry.length else 0.5
        ratio = max(0.0, min(1.0, ratio))
        virtual_node = next_node
        next_node += 1
        graph.add_node(virtual_node, x=float(point.x), y=float(point.y), venue_id=item["venue_id"], venue_access="virtual")

        total_length = float(data.get("length", 0.0))
        start_point = (graph.nodes[u]["x"], graph.nodes[u]["y"])
        end_point = (graph.nodes[v]["x"], graph.nodes[v]["y"])
        virtual_point = (float(point.x), float(point.y))
        to_virtual = LineString([start_point, virtual_point])
        from_virtual = LineString([virtual_point, start_point])
        to_end = LineString([virtual_point, end_point])
        from_end = LineString([end_point, virtual_point])
        attrs = {"osmid": -virtual_node, "highway": "venue_access", "oneway": False}
        graph.add_edge(u, virtual_node, **attrs, length=round(total_length * ratio, 6), geometry=to_virtual)
        graph.add_edge(virtual_node, u, **attrs, length=round(total_length * ratio, 6), geometry=from_virtual)
        graph.add_edge(virtual_node, v, **attrs, length=round(total_length * (1 - ratio), 6), geometry=to_end)
        graph.add_edge(v, virtual_node, **attrs, length=round(total_length * (1 - ratio), 6), geometry=from_end)

        physical_key = (min(u, v), max(u, v))
        physical_groups.setdefault(physical_key, []).append((ratio, virtual_node, point))
        updated = dict(item)
        updated["base_graph_node"] = item["node"]
        updated["node"] = virtual_node
        updated["access_method"] = "virtual_node_on_nearest_pedestrian_edge"
        new_access.append(updated)

    for (_u, _v), points in physical_groups.items():
        points.sort(key=lambda value: value[0])
        for left, right in zip(points, points[1:]):
            _, left_node, left_point = left
            _, right_node, right_point = right
            length = ((left_point.x - right_point.x) ** 2 + (left_point.y - right_point.y) ** 2) ** 0.5 * 111_000
            attrs = {"osmid": -1, "highway": "venue_access", "oneway": False, "length": length}
            graph.add_edge(left_node, right_node, **attrs, geometry=LineString([left_point, right_point]))
            graph.add_edge(right_node, left_node, **attrs, geometry=LineString([right_point, left_point]))

    ox.save_graphml(graph, GRAPH_PATH)
    ACCESS_PATH.write_text(json.dumps(new_access, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if REPORT_PATH.exists():
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        report["nodes"] = graph.number_of_nodes()
        report["edges"] = graph.number_of_edges()
        report["virtual_access_nodes"] = len(new_access)
        report["venue_access_model"] = "one virtual graph node per venue projected onto the nearest pedestrian edge"
        report["limitations"][0] = "Venue points for ways/relations originate from OSM centers, then receive independent virtual access nodes on the pedestrian network."
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"venues": len(new_access), "virtual_nodes": len(new_access), "graph_nodes": graph.number_of_nodes(), "graph_edges": graph.number_of_edges()}))


if __name__ == "__main__":
    main()
