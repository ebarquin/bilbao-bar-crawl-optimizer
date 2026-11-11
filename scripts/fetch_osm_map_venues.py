#!/usr/bin/env python3
"""Fetch candidate venue data from the standard OSM map API and filter locally."""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from shapely.geometry import Point, shape


ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://api.openstreetmap.org/api/0.6/map"
AMENITIES = {"bar", "pub", "cafe", "biergarten"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--area", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--xml-output", type=Path, required=True)
    args = parser.parse_args()

    area = json.loads(args.area.read_text(encoding="utf-8"))
    polygon = shape(area["features"][0]["geometry"])
    min_lon, min_lat, max_lon, max_lat = polygon.bounds
    url = f"{ENDPOINT}?bbox={min_lon:.7f},{min_lat:.7f},{max_lon:.7f},{max_lat:.7f}"
    request = Request(url, headers={"User-Agent": "BilbaoBarCrawlOptimizer/0.1 (research project)"})
    with urlopen(request, timeout=240) as response:
        xml_bytes = response.read()
    args.xml_output.parent.mkdir(parents=True, exist_ok=True)
    args.xml_output.write_bytes(xml_bytes)

    root = ET.fromstring(xml_bytes)
    node_coords = {}
    elements = []
    for element in root:
        if element.tag == "node":
            point = (float(element.attrib["lon"]), float(element.attrib["lat"]))
            node_coords[int(element.attrib["id"])] = point
            tags = {tag.attrib["k"]: tag.attrib["v"] for tag in element.findall("tag")}
            if tags.get("amenity") in AMENITIES and polygon.covers(Point(point)):
                elements.append({"type": "node", "id": int(element.attrib["id"]), "lat": point[1], "lon": point[0], "tags": tags})
        
    for element in root.findall("way"):
        tags = {tag.attrib["k"]: tag.attrib["v"] for tag in element.findall("tag")}
        if tags.get("amenity") not in AMENITIES:
            continue
        points = [node_coords.get(int(nd.attrib["ref"])) for nd in element.findall("nd")]
        points = [point for point in points if point]
        if not points:
            continue
        center = (sum(point[0] for point in points) / len(points), sum(point[1] for point in points) / len(points))
        if polygon.covers(Point(center)):
            elements.append({"type": "way", "id": int(element.attrib["id"]), "center": {"lat": center[1], "lon": center[0]}, "tags": tags})

    result = {
        "version": 0.6,
        "generator": "OpenStreetMap map API",
        "elements": elements,
        "_bilbao_metadata": {
            "endpoint": ENDPOINT,
            "request_url": url,
            "source": "OpenStreetMap standard map API",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "study_area": str(args.area.relative_to(ROOT)) if args.area.is_relative_to(ROOT) else str(args.area),
            "filter": "amenity in bar, pub, cafe, biergarten; center filtered locally against study polygon",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"osm_elements": len(root), "venue_elements": len(elements), "xml": str(args.xml_output), "json": str(args.output)}))


if __name__ == "__main__":
    main()
