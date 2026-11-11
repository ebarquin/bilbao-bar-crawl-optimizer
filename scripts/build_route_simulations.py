#!/usr/bin/env python3
"""Export algorithm routes as GeoJSON and transparent time simulations."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
import osmnx as ox
from shapely.geometry import LineString, mapping


ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "data/processed/optimization-results.json"
MATRIX_PATH = ROOT / "data/processed/distance-matrix.json"
GRAPH_PATH = ROOT / "data/processed/pedestrian-network.graphml"
ACCESS_PATH = ROOT / "data/processed/venue-access.json"
CONFIG_PATH = ROOT / "data/study-areas/routing-config.json"
ROUTES_PATH = ROOT / "data/processed/optimization-routes.geojson"
SIMULATIONS_PATH = ROOT / "data/processed/optimization-simulations.json"


def edge_geometry(graph, u, v):
    bundle = graph.get_edge_data(u, v)
    key, data = min(bundle.items(), key=lambda item: item[1].get("length", float("inf")))
    geometry = data.get("geometry")
    if geometry is None:
        geometry = LineString([(graph.nodes[u]["x"], graph.nodes[u]["y"]), (graph.nodes[v]["x"], graph.nodes[v]["y"])])
    return geometry, key, float(data.get("length", 0))


def best_records(results: dict) -> list[dict]:
    selected = []
    for algorithm in sorted({record["algorithm"] for record in results["algorithms"]}):
        group = [record for record in results["algorithms"] if record["algorithm"] == algorithm]
        selected.append(min(group, key=lambda record: record["distance_m"]))
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=RESULTS_PATH)
    parser.add_argument("--matrix", type=Path, default=MATRIX_PATH)
    parser.add_argument("--graph", type=Path, default=GRAPH_PATH)
    parser.add_argument("--access", type=Path, default=ACCESS_PATH)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    args = parser.parse_args()

    results = json.loads(args.results.read_text(encoding="utf-8"))
    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    config = json.loads(args.config.read_text(encoding="utf-8"))
    graph = ox.load_graphml(args.graph)
    access = json.loads(args.access.read_text(encoding="utf-8"))
    venue_nodes = {item["venue_id"]: int(item["node"]) for item in access}
    venue_names = {item["venue_id"]: item["name"] for item in access}
    start_node = int(results["start_node"])
    speed_m_per_min = config["walking_speed_kmh"] * 1000 / 60
    stop_duration = float(config["stop_duration_min"])
    daily_duration = float(config["daily_duration_min"])
    route_features = []
    simulations = []

    for record in best_records(results):
        algorithm = record["algorithm"]
        order = record["order"]
        leg_specs = []
        first_node = venue_nodes[order[0]]
        leg_specs.append(("Plaza Nueva", "plaza-nueva", order[0], start_node, first_node, [start_node] + nx.shortest_path(graph, start_node, first_node, weight="length")[1:]))
        for origin, destination in zip(order, order[1:]):
            path = matrix["routes"][origin][destination]
            if path is None:
                raise RuntimeError(f"No route for {origin} -> {destination}")
            leg_specs.append((venue_names[origin], origin, destination, int(venue_nodes[origin]), int(venue_nodes[destination]), path))

        cumulative_walk = 0.0
        cumulative_stop = 0.0
        for leg_index, (origin_name, origin_id, destination_id, _origin_node, _destination_node, path) in enumerate(leg_specs):
            for edge_index, (u, v) in enumerate(zip(path, path[1:])):
                geometry, edge_key, length_m = edge_geometry(graph, u, v)
                cumulative_walk += length_m
                route_features.append({
                    "type": "Feature",
                    "properties": {
                        "algorithm": algorithm,
                        "leg_index": leg_index,
                        "edge_index": edge_index,
                        "origin_id": origin_id,
                        "origin_name": origin_name,
                        "destination_id": destination_id,
                        "destination_name": venue_names[destination_id],
                        "length_m": round(length_m, 2),
                        "cumulative_walking_min": round(cumulative_walk / speed_m_per_min, 2),
                        "edge_key": edge_key,
                    },
                    "geometry": mapping(geometry),
                })
            cumulative_stop += stop_duration

        total_walking_min = cumulative_walk / speed_m_per_min
        total_stop_min = len(order) * stop_duration
        total_duration = total_walking_min + total_stop_min
        simulations.append({
            "algorithm": algorithm,
            "seed": record.get("seed"),
            "scenario": config["scenario"],
            "start": config["start"]["name"],
            "end": "free",
            "venue_count": len(order),
            "distance_m": round(cumulative_walk, 2),
            "walking_time_min": round(total_walking_min, 2),
            "stop_duration_min_per_venue": stop_duration,
            "stop_time_min": round(total_stop_min, 2),
            "total_duration_min": round(total_duration, 2),
            "estimated_days": math.ceil(total_duration / daily_duration),
            "daily_duration_min": daily_duration,
            "parameters_are_estimates": True,
        })

    ROUTES_PATH.write_text(json.dumps({"type": "FeatureCollection", "features": route_features}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "simulations": simulations,
        "limitations": [
            "Stop duration is a configurable assumption, not an observed measurement.",
            "Walking time uses a constant configurable speed and excludes opening hours or waiting time.",
            "The route geometries come from the cached pedestrian graph and matrix.",
        ],
    }
    SIMULATIONS_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"algorithms": len(simulations), "route_features": len(route_features), "simulations_file": str(SIMULATIONS_PATH)}))


if __name__ == "__main__":
    main()
