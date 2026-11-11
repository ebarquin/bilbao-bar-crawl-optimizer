#!/usr/bin/env python3
"""Compare reproducible route heuristics on the cached pedestrian matrix."""

from __future__ import annotations

import argparse
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
import osmnx as ox
from ortools.constraint_solver import pywrapcp, routing_enums_pb2


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "data/processed/distance-matrix.json"
GRAPH_PATH = ROOT / "data/processed/pedestrian-network.graphml"
CONFIG_PATH = ROOT / "data/study-areas/routing-config.json"
RESULTS_PATH = ROOT / "data/processed/optimization-results.json"
SUMMARY_PATH = ROOT / "data/processed/optimization-summary.json"


def route_distance(order: list[str], distances: dict, start_distances: dict) -> float:
    if not order:
        return 0.0
    total = start_distances[order[0]]
    total += sum(distances[a][b] for a, b in zip(order, order[1:]))
    return total


def nearest_neighbor(venue_ids: list[str], distances: dict, start_distances: dict, first: str | None = None) -> list[str]:
    remaining = set(venue_ids)
    current = first
    if current is None:
        current = min(remaining, key=lambda venue: (start_distances[venue], venue))
    remaining.remove(current)
    order = [current]
    while remaining:
        current = min(remaining, key=lambda venue: (distances[order[-1]][venue], venue))
        remaining.remove(current)
        order.append(current)
    return order


def two_opt(order: list[str], distances: dict, start_distances: dict) -> list[str]:
    best = order[:]
    best_distance = route_distance(best, distances, start_distances)
    improved = True
    while improved:
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 1, len(best)):
                candidate = best[:i] + list(reversed(best[i : j + 1])) + best[j + 1 :]
                candidate_distance = route_distance(candidate, distances, start_distances)
                if candidate_distance + 0.01 < best_distance:
                    best, best_distance, improved = candidate, candidate_distance, True
        
    return best


def ortools_route(venue_ids: list[str], distances: dict, start_distances: dict) -> list[str]:
    # Index 0 is Plaza Nueva; 1..n are venues; n+1 is a zero-cost free end.
    end_index = len(venue_ids) + 1
    manager = pywrapcp.RoutingIndexManager(len(venue_ids) + 2, 1, [0], [end_index])
    routing = pywrapcp.RoutingModel(manager)
    scale = 100

    def cost_callback(from_index: int, to_index: int) -> int:
        origin = manager.IndexToNode(from_index)
        destination = manager.IndexToNode(to_index)
        if origin == end_index or destination == end_index:
            return 0
        if origin == 0:
            value = start_distances[venue_ids[destination - 1]]
        else:
            value = distances[venue_ids[origin - 1]][venue_ids[destination - 1]]
        return int(round(value * scale))

    transit_callback = routing.RegisterTransitCallback(cost_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback)
    search = pywrapcp.DefaultRoutingSearchParameters()
    search.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search.time_limit.seconds = 10
    solution = routing.SolveWithParameters(search)
    if solution is None:
        raise RuntimeError("OR-Tools did not return a solution")
    index = routing.Start(0)
    order = []
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        if node > 0:
            order.append(venue_ids[node - 1])
        index = solution.Value(routing.NextVar(index))
    return order


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, default=MATRIX_PATH)
    parser.add_argument("--graph", type=Path, default=GRAPH_PATH)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    args = parser.parse_args()

    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    config = json.loads(args.config.read_text(encoding="utf-8"))
    graph = ox.load_graphml(args.graph)
    venue_ids = matrix["venue_ids"]
    distances = matrix["distances_m"]
    speed = config["walking_speed_kmh"]
    start_lon, start_lat = config["start"]["coordinates"]
    largest_component = max(nx.weakly_connected_components(graph), key=len)
    start_node = min(largest_component, key=lambda node: (graph.nodes[node]["x"] - start_lon) ** 2 + (graph.nodes[node]["y"] - start_lat) ** 2)
    start_lengths = nx.single_source_dijkstra_path_length(graph, start_node, weight="length")
    access = json.loads((ROOT / "data/processed/venue-access.json").read_text(encoding="utf-8"))
    venue_nodes = {item["venue_id"]: int(item["node"]) for item in access}
    start_distances = {venue_id: float(start_lengths[venue_nodes[venue_id]]) for venue_id in venue_ids}

    records = []

    def add_record(name: str, order: list[str], started: float, seed: int | None = None, note: str | None = None):
        distance = route_distance(order, distances, start_distances)
        records.append({
            "algorithm": name,
            "seed": seed,
            "note": note,
            "scenario": config["scenario"],
            "start": config["start"]["name"],
            "end": "free",
            "venue_count": len(order),
            "distance_m": round(distance, 2),
            "walking_time_min": round(distance / (speed * 1000 / 60), 2),
            "runtime_ms": round((time.perf_counter() - started) * 1000, 2),
            "order": order,
        })

    for seed in config["random_seeds"]:
        started = time.perf_counter()
        rng = random.Random(seed)
        order = venue_ids[:]
        rng.shuffle(order)
        add_record("random", order, started, seed=seed)

    started = time.perf_counter()
    nn_order = nearest_neighbor(venue_ids, distances, start_distances)
    add_record("nearest_neighbor", nn_order, started)

    started = time.perf_counter()
    candidates = [(venue, nearest_neighbor(venue_ids, distances, start_distances, first=venue)) for venue in venue_ids]
    multi_order = min(candidates, key=lambda pair: (route_distance(pair[1], distances, start_distances), pair[0]))[1]
    add_record("nearest_neighbor_multi_start", multi_order, started, note="Compara cada establecimiento como primer destino después de Plaza Nueva.")

    started = time.perf_counter()
    improved_order = two_opt(nn_order, distances, start_distances)
    add_record("two_opt", improved_order, started, note="2-opt sobre la solución Nearest Neighbor; costes dirigidos evaluados explícitamente.")

    started = time.perf_counter()
    ortools_order = ortools_route(venue_ids, distances, start_distances)
    add_record("or_tools", ortools_order, started, note="Modelo TSP abierto con final libre mediante nodo final de coste cero.")

    random_records = [record for record in records if record["algorithm"] == "random"]
    random_mean = sum(record["distance_m"] for record in random_records) / len(random_records)
    random_best = min(record["distance_m"] for record in random_records)
    summary = []
    for algorithm in sorted(set(record["algorithm"] for record in records)):
        group = [record for record in records if record["algorithm"] == algorithm]
        best = min(group, key=lambda record: record["distance_m"])
        summary.append({
            "algorithm": algorithm,
            "runs": len(group),
            "best_distance_m": best["distance_m"],
            "best_walking_time_min": best["walking_time_min"],
            "mean_distance_m": round(sum(record["distance_m"] for record in group) / len(group), 2),
            "improvement_vs_random_mean_pct": round((1 - best["distance_m"] / random_mean) * 100, 2),
            "improvement_vs_random_best_pct": round((1 - best["distance_m"] / random_best) * 100, 2),
        })

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "start_node": int(start_node),
        "start_graph_point": [graph.nodes[start_node]["x"], graph.nodes[start_node]["y"]],
        "algorithms": records,
        "summary": summary,
        "interpretation": "Los resultados son soluciones encontradas bajo el escenario abierto; no implican optimalidad global.",
    }
    RESULTS_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SUMMARY_PATH.write_text(json.dumps({"generated_at": output["generated_at"], "scenario": config["scenario"], "summary": summary}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(records), "summary": summary, "results_file": str(RESULTS_PATH)}))


if __name__ == "__main__":
    main()
