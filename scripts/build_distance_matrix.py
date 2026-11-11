#!/usr/bin/env python3
"""Build a reusable directed pedestrian distance matrix."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
import osmnx as ox


ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = ROOT / "data/processed/pedestrian-network.graphml"
ACCESS_PATH = ROOT / "data/processed/venue-access.json"
MATRIX_PATH = ROOT / "data/processed/distance-matrix.json"
REPORT_PATH = ROOT / "data/processed/distance-matrix-report.json"
DEFAULT_SPEED_KMH = 4.5


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", type=Path, default=GRAPH_PATH)
    parser.add_argument("--access", type=Path, default=ACCESS_PATH)
    parser.add_argument("--speed-kmh", type=float, default=DEFAULT_SPEED_KMH)
    args = parser.parse_args()
    if args.speed_kmh <= 0:
        raise ValueError("Walking speed must be positive")

    graph = ox.load_graphml(args.graph)
    access = json.loads(args.access.read_text(encoding="utf-8"))
    access = sorted(access, key=lambda item: item["venue_id"])
    venue_ids = [item["venue_id"] for item in access]
    venue_nodes = {item["venue_id"]: int(item["node"]) for item in access}
    node_groups = {}
    for item in access:
        node_groups.setdefault(str(item["node"]), []).append(item["venue_id"])

    distances_m = {origin: {} for origin in venue_ids}
    times_min = {origin: {} for origin in venue_ids}
    routes = {origin: {} for origin in venue_ids}
    source_cache = {}
    unreachable_pairs = []
    speed_m_per_min = args.speed_kmh * 1000 / 60

    for origin_id in venue_ids:
        origin_node = venue_nodes[origin_id]
        if origin_node not in source_cache:
            lengths, paths = nx.single_source_dijkstra(graph, origin_node, weight="length")
            source_cache[origin_node] = (lengths, paths)
        lengths, paths = source_cache[origin_node]
        for destination_id in venue_ids:
            destination_node = venue_nodes[destination_id]
            distance = lengths.get(destination_node)
            distances_m[origin_id][destination_id] = round(float(distance), 2) if distance is not None else None
            times_min[origin_id][destination_id] = round(float(distance) / speed_m_per_min, 2) if distance is not None else None
            if destination_node in paths:
                routes[origin_id][destination_id] = [int(node) for node in paths[destination_node]]
            else:
                routes[origin_id][destination_id] = None
                if origin_id != destination_id:
                    unreachable_pairs.append([origin_id, destination_id])

    asymmetric_pairs = []
    for index, origin in enumerate(venue_ids):
        for destination in venue_ids[index + 1 :]:
            forward = distances_m[origin][destination]
            backward = distances_m[destination][origin]
            if forward is not None and backward is not None and abs(forward - backward) > 0.1:
                asymmetric_pairs.append({"origin": origin, "destination": destination, "forward_m": forward, "backward_m": backward})

    matrix = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "graph_file": str(args.graph.relative_to(ROOT)),
        "access_file": str(args.access.relative_to(ROOT)),
        "walking_speed_kmh": args.speed_kmh,
        "venue_ids": venue_ids,
        "venue_nodes": venue_nodes,
        "distances_m": distances_m,
        "walking_time_min": times_min,
        "routes": routes,
    }
    MATRIX_PATH.write_text(json.dumps(matrix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = {
        "generated_at": matrix["generated_at"],
        "venues": len(venue_ids),
        "unique_access_nodes": len(set(venue_nodes.values())),
        "same_node_groups": [group for group in node_groups.values() if len(group) > 1],
        "ordered_pairs": len(venue_ids) ** 2,
        "reachable_ordered_pairs": sum(value is not None for row in distances_m.values() for value in row.values()),
        "unreachable_ordered_pairs": len(unreachable_pairs),
        "unreachable_pairs": unreachable_pairs,
        "asymmetric_unordered_pairs": len(asymmetric_pairs),
        "asymmetric_examples": asymmetric_pairs[:20],
        "walking_speed_kmh": args.speed_kmh,
        "route_reconstruction": "Each matrix cell stores the ordered graph node sequence; edge geometries remain in the cached GraphML graph.",
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "venues": report["venues"],
        "reachable_ordered_pairs": report["reachable_ordered_pairs"],
        "unreachable_ordered_pairs": report["unreachable_ordered_pairs"],
        "asymmetric_unordered_pairs": report["asymmetric_unordered_pairs"],
        "matrix_file": str(MATRIX_PATH),
    }))


if __name__ == "__main__":
    main()
