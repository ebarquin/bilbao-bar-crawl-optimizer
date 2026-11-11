#!/usr/bin/env python3
"""Normalize cached Overpass venues into GeoJSON plus a quality report."""

from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/raw/overpass-casco-viejo-bilbao.json"
DEFAULT_OUTPUT = ROOT / "data/processed/venues.geojson"
DEFAULT_REPORT = ROOT / "data/processed/quality-report.json"
CATEGORY_LABELS = {
    "bar": "bar",
    "pub": "pub",
    "cafe": "cafetería",
    "biergarten": "cervecería",
}


def slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def coordinates(element: dict) -> tuple[float, float] | None:
    if "lat" in element and "lon" in element:
        return float(element["lon"]), float(element["lat"])
    center = element.get("center")
    if center and "lat" in center and "lon" in center:
        return float(center["lon"]), float(center["lat"])
    return None


def distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat = math.radians((a[1] + b[1]) / 2)
    dx = (a[0] - b[0]) * 111_320 * math.cos(lat)
    dy = (a[1] - b[1]) * 110_540
    return math.hypot(dx, dy)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    source = json.loads(args.input.read_text(encoding="utf-8"))
    captured_at = source.get("_bilbao_metadata", {}).get("captured_at")
    source_label = source.get("_bilbao_metadata", {}).get("source", "OpenStreetMap via Overpass API")
    elements = source.get("elements", [])
    features = []
    skipped = []
    seen = set()
    for element in elements:
        tags = element.get("tags", {})
        amenity = tags.get("amenity")
        point = coordinates(element)
        identity = (element.get("type"), element.get("id"))
        if identity in seen:
            continue
        seen.add(identity)
        if not point or amenity not in CATEGORY_LABELS:
            skipped.append({"id": identity, "reason": "missing coordinates or unsupported amenity"})
            continue
        name = tags.get("name") or tags.get("name:es") or f"OSM {element['type']} {element['id']}"
        features.append({
            "type": "Feature",
            "id": f"{element['type']}/{element['id']}",
            "properties": {
                "osm_type": element["type"],
                "osm_id": element["id"],
                "name": name,
                "category": CATEGORY_LABELS[amenity],
                "amenity": amenity,
                "source": source_label,
                "captured_at": captured_at,
                "location_type": "node" if element["type"] == "node" else "center_of_way_or_relation",
                "tags": tags,
            },
            "geometry": {"type": "Point", "coordinates": list(point)},
        })

    name_groups: dict[str, list[dict]] = defaultdict(list)
    for feature in features:
        name_groups[slug(feature["properties"]["name"])].append(feature)
    duplicate_candidates = []
    for key, group in name_groups.items():
        if not key or len(group) < 2:
            continue
        for i, first in enumerate(group):
            for second in group[i + 1 :]:
                a = tuple(first["geometry"]["coordinates"])
                b = tuple(second["geometry"]["coordinates"])
                duplicate_candidates.append({
                    "name_key": key,
                    "ids": [first["id"], second["id"]],
                    "distance_m": round(distance_m(a, b), 1),
                })

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_file": str(args.input.relative_to(ROOT)),
        "source_captured_at": captured_at,
        "query_scope": ["bar", "pub", "cafe", "biergarten"],
        "total_elements": len(elements),
        "exported_features": len(features),
        "skipped_elements": len(skipped),
        "category_counts": dict(Counter(f["properties"]["category"] for f in features)),
        "duplicate_candidates": duplicate_candidates,
        "manual_validation_required": True,
        "limitations": [
            "OSM coverage and names can be incomplete or stale.",
            "Ways and relations use their OSM center, not necessarily an entrance.",
            "Restaurants and other amenities are not included in this first query.",
        ],
    }
    output = {"type": "FeatureCollection", "name": "bilbao-venues", "features": features}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(features)} venues to {args.output}")
    print(f"Quality report written to {args.report}")


if __name__ == "__main__":
    main()
