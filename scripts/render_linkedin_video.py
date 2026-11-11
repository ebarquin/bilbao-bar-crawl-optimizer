#!/usr/bin/env python3
"""Render a short LinkedIn video from the cached pedestrian route artifacts."""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import networkx as nx
import numpy as np
import osmnx as ox


ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = ROOT / "data/processed/pedestrian-network.graphml"
ACCESS_PATH = ROOT / "data/processed/venue-access.json"
VENUES_PATH = ROOT / "data/processed/venues.geojson"
ROUTES_PATH = ROOT / "data/processed/optimization-routes.geojson"
AREA_PATH = ROOT / "data/study-areas/casco-viejo-bilbao.geojson"
OUTPUT_PATH = ROOT / "media/bilbao-bar-crawl-linkedin.mp4"

WIDTH, HEIGHT = 1080, 1350
FPS = 24
DURATION = 20
MAP_BOX = (55, 285, 1025, 1090)
CATEGORY_COLORS = {"bar": (255, 90, 67), "cafetería": (0, 184, 169), "pub": (245, 184, 46)}
FONT = {
    "A": "01110/10001/10001/11111/10001/10001/10001", "B": "11110/10001/10001/11110/10001/10001/11110",
    "C": "01111/10000/10000/10000/10000/10000/01111", "D": "11110/10001/10001/10001/10001/10001/11110",
    "E": "11111/10000/10000/11110/10000/10000/11111", "F": "11111/10000/10000/11110/10000/10000/10000",
    "G": "01111/10000/10000/10111/10001/10001/01111", "H": "10001/10001/10001/11111/10001/10001/10001",
    "I": "11111/00100/00100/00100/00100/00100/11111", "J": "00111/00010/00010/00010/10010/10010/01100",
    "K": "10001/10010/10100/11000/10100/10010/10001", "L": "10000/10000/10000/10000/10000/10000/11111",
    "M": "10001/11011/10101/10101/10001/10001/10001", "N": "10001/11001/10101/10011/10001/10001/10001",
    "O": "01110/10001/10001/10001/10001/10001/01110", "P": "11110/10001/10001/11110/10000/10000/10000",
    "Q": "01110/10001/10001/10001/10101/10010/01101", "R": "11110/10001/10001/11110/10100/10010/10001",
    "S": "01111/10000/10000/01110/00001/00001/11110", "T": "11111/00100/00100/00100/00100/00100/00100",
    "U": "10001/10001/10001/10001/10001/10001/01110", "V": "10001/10001/10001/10001/10001/01010/00100",
    "W": "10001/10001/10001/10101/10101/11011/10001", "X": "10001/10001/01010/00100/01010/10001/10001",
    "Y": "10001/10001/01010/00100/00100/00100/00100", "Z": "11111/00001/00010/00100/01000/10000/11111",
    "0": "01110/10001/10011/10101/11001/10001/01110", "1": "00100/01100/00100/00100/00100/00100/01110",
    "2": "01110/10001/00001/00010/00100/01000/11111", "3": "11110/00001/00001/01110/00001/00001/11110",
    "4": "00010/00110/01010/10010/11111/00010/00010", "5": "11111/10000/10000/11110/00001/00001/11110",
    "6": "01110/10000/10000/11110/10001/10001/01110", "7": "11111/00001/00010/00100/01000/01000/01000",
    "8": "01110/10001/10001/01110/10001/10001/01110", "9": "01110/10001/10001/01111/00001/00001/01110",
    "-": "00000/00000/00000/11111/00000/00000/00000", "|": "00100/00100/00100/00100/00100/00100/00100",
    ".": "00000/00000/00000/00000/00000/00110/00110", ",": "00000/00000/00000/00000/00110/00110/00100",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def geometry_coords(geometry):
    if geometry["type"] == "LineString":
        return geometry["coordinates"]
    return [point for line in geometry["coordinates"] for point in line]


def draw_line(image, points, color, width=1):
    if len(points) < 2:
        return
    radius = max(0, width // 2)
    for start, end in zip(points, points[1:]):
        x0, y0 = start
        x1, y1 = end
        steps = max(abs(x1 - x0), abs(y1 - y0)) + 1
        xs = np.linspace(x0, x1, steps, dtype=np.int32)
        ys = np.linspace(y0, y1, steps, dtype=np.int32)
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                xx = np.clip(xs + dx, 0, WIDTH - 1)
                yy = np.clip(ys + dy, 0, HEIGHT - 1)
                image[yy, xx] = color


def draw_circle(image, x, y, radius, color, outline=None):
    y0, y1 = max(0, y - radius), min(HEIGHT, y + radius + 1)
    x0, x1 = max(0, x - radius), min(WIDTH, x + radius + 1)
    yy, xx = np.ogrid[y0:y1, x0:x1]
    mask = (xx - x) ** 2 + (yy - y) ** 2 <= radius ** 2
    if outline:
        outer = (xx - x) ** 2 + (yy - y) ** 2 <= (radius + 2) ** 2
        image[y0:y1, x0:x1][outer] = outline
    image[y0:y1, x0:x1][mask] = color


def draw_text(image, text, x, y, scale, color):
    cursor = x
    for character in text.upper():
        if character == " ":
            cursor += 4 * scale
            continue
        pattern = FONT.get(character)
        if pattern is None:
            cursor += 6 * scale
            continue
        rows = pattern.split("/")
        for row, bits in enumerate(rows):
            for column, bit in enumerate(bits):
                if bit == "1":
                    x0 = cursor + column * scale
                    y0 = y + row * scale
                    image[y0:y0 + scale, x0:x0 + scale] = color
        cursor += 6 * scale


def main():
    graph = ox.load_graphml(GRAPH_PATH)
    access = load_json(ACCESS_PATH)
    venues = load_json(VENUES_PATH)
    routes = load_json(ROUTES_PATH)
    area = load_json(AREA_PATH)
    route_features = [feature for feature in routes["features"] if feature["properties"]["algorithm"] == "or_tools"]
    route_features.sort(key=lambda feature: (feature["properties"]["leg_index"], feature["properties"]["edge_index"]))

    all_coords = []
    for feature in area["features"]:
        def walk(value):
            if isinstance(value, list) and value and isinstance(value[0], (int, float)):
                all_coords.append(value)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        walk(feature["geometry"]["coordinates"])
    for feature in route_features:
        all_coords.extend(geometry_coords(feature["geometry"]))
    for item in access:
        all_coords.append(item["street_point"])

    min_lon = min(point[0] for point in all_coords)
    max_lon = max(point[0] for point in all_coords)
    min_lat = min(point[1] for point in all_coords)
    max_lat = max(point[1] for point in all_coords)
    left, top, right, bottom = MAP_BOX

    def project(point):
        x = int(left + (point[0] - min_lon) / (max_lon - min_lon) * (right - left))
        y = int(bottom - (point[1] - min_lat) / (max_lat - min_lat) * (bottom - top))
        return x, y

    base = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    base[:] = (7, 31, 36)
    base[top:bottom, left:right] = (10, 48, 53)

    # Draw the cached pedestrian network as a subtle context layer.
    for u, v, data in graph.edges(data=True):
        geometry = data.get("geometry")
        if geometry is not None:
            coords = list(geometry.coords)
        else:
            coords = [(graph.nodes[u]["x"], graph.nodes[u]["y"]), (graph.nodes[v]["x"], graph.nodes[v]["y"])]
        draw_line(base, [project(point) for point in coords], (25, 75, 79), 1)

    # Perimeter and establishments.
    for feature in area["features"]:
        coords = feature["geometry"]["coordinates"][0]
        draw_line(base, [project(point) for point in coords], (92, 190, 178), 2)
    categories = {feature["id"]: feature["properties"].get("category") for feature in venues["features"]}
    venue_points = [(project(item["street_point"]), CATEGORY_COLORS.get(categories.get(item["venue_id"]), (190, 220, 210))) for item in access]
    for (x, y), color in venue_points:
        draw_circle(base, x, y, 5, color, outline=(255, 255, 255))

    route = []
    for feature in route_features:
        for point in geometry_coords(feature["geometry"]):
            projected = project(point)
            if not route or projected != route[-1]:
                route.append(projected)
    cumulative = [0.0]
    for a, b in zip(route, route[1:]):
        cumulative.append(cumulative[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    total_length = cumulative[-1]

    draw_text(base, "BILBAO BAR CRAWL OPTIMIZER", 55, 58, 3, (184, 229, 222))
    draw_text(base, "LA RUTA OR-TOOLS POR EL CASCO VIEJO", 55, 108, 4, (255, 255, 255))
    draw_text(base, "157 ESTABLECIMIENTOS | 7,66 KM | 1 H 42 MIN", 55, 1168, 2, (209, 227, 224))
    draw_text(base, "15 MIN POR PARADA PARA TOMAR UN VINO", 55, 1210, 2, (255, 138, 105))
    command = [
        "ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p", str(OUTPUT_PATH),
    ]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    try:
        for frame in range(FPS * DURATION):
            image = base.copy()
            progress = min(1.0, frame / max(1, FPS * (DURATION - 2)))
            target = total_length * progress
            index = next((i for i, distance in enumerate(cumulative) if distance >= target), len(route) - 1)
            if index < 1:
                index = 1
            previous = cumulative[index - 1]
            segment = cumulative[index] - previous or 1
            blend = (target - previous) / segment
            current = (
                int(route[index - 1][0] + (route[index][0] - route[index - 1][0]) * blend),
                int(route[index - 1][1] + (route[index][1] - route[index - 1][1]) * blend),
            )
            draw_line(image, route[:index] + [current], (255, 90, 67), 5)
            draw_circle(image, *current, 10, (255, 90, 67), outline=(255, 255, 255))
            process.stdin.write(image.tobytes())
    finally:
        process.stdin.close()
        return_code = process.wait()
    if return_code:
        raise SystemExit(return_code)
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
