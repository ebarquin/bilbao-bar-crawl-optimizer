#!/usr/bin/env python3
"""Fetch the study area's OSM venues from Overpass and cache the response."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AREA = ROOT / "data/study-areas/casco-viejo-bilbao.geojson"
DEFAULT_OUTPUT = ROOT / "data/raw/overpass-casco-viejo-bilbao.json"
ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)


def polygon_text(area: dict) -> str:
    coordinates = area["features"][0]["geometry"]["coordinates"][0]
    return " ".join(f"{lat} {lon}" for lon, lat in coordinates)


def build_query(area: dict) -> str:
    poly = polygon_text(area)
    return f"""[out:json][timeout:180];
(
  nwr[\"amenity\"~\"^(bar|pub|cafe|biergarten)$\"](poly:\"{poly}\");
);
out center tags qt;"""


def fetch(query: str, endpoint: str) -> dict:
    payload = urlencode({"data": query}).encode("utf-8")
    request = Request(
        endpoint,
        data=payload,
        headers={
            "User-Agent": "BilbaoBarCrawlOptimizer/0.1 (research project)",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        },
    )
    with urlopen(request, timeout=240) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--area", type=Path, default=DEFAULT_AREA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--endpoint", choices=ENDPOINTS, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.output.exists() and not args.force:
        print(f"Using cached response: {args.output}")
        return

    area = json.loads(args.area.read_text(encoding="utf-8"))
    query = build_query(area)
    endpoints = (args.endpoint,) if args.endpoint else ENDPOINTS
    result = None
    used_endpoint = None
    for endpoint in endpoints:
        try:
            print(f"Querying Overpass: {endpoint}")
            result = fetch(query, endpoint)
            used_endpoint = endpoint
            break
        except Exception as error:
            print(f"Endpoint failed: {error}")
    if result is None:
        raise RuntimeError("No Overpass endpoint returned a usable response")
    result["_bilbao_metadata"] = {
        "endpoint": used_endpoint,
        "query": query,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "study_area": str(args.area.relative_to(ROOT)),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(result.get('elements', []))} OSM elements to {args.output}")
    time.sleep(1)


if __name__ == "__main__":
    main()
