import json
import time
from pathlib import Path

import requests


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OUTPUT_PATH = Path("assets/baku-districts.geojson")
USER_AGENT = "BakuHousePriceResearch/1.0 (district map for educational app)"

DISTRICT_QUERIES = {
    "Absheron": "Ab\u015feron rayonu, Az\u0259rbaycan",
    "Binagadi": "Bin\u0259q\u0259di rayonu, Az\u0259rbaycan",
    "Garadagh": "Qarada\u011f rayonu, Az\u0259rbaycan",
    "Khatai": "X\u0259tai rayonu, Az\u0259rbaycan",
    "Khazar": "X\u0259z\u0259r rayonu, Az\u0259rbaycan",
    "Narimanov": "N\u0259rimanov rayonu, Az\u0259rbaycan",
    "Nasimi": "N\u0259simi rayonu, Az\u0259rbaycan",
    "Nizami": "Nizami raion, Baku, Azerbaijan",
    "Sabunchu": "Sabun\u00e7u rayonu, Az\u0259rbaycan",
    "Sabail": "S\u0259bail rayonu, Az\u0259rbaycan",
    "Surakhani": "Suraxan\u0131 rayonu, Az\u0259rbaycan",
    "Yasamal": "Yasamal rayonu, Az\u0259rbaycan",
}


def fetch_polygon(session, district, query):
    response = session.get(
        NOMINATIM_URL,
        params={
            "q": query,
            "format": "jsonv2",
            "polygon_geojson": 1,
            "limit": 10,
        },
        timeout=30,
    )
    response.raise_for_status()
    results = response.json()
    if not results:
        raise RuntimeError(f"No boundary found for {district}")

    boundary = next(
        (
            result
            for result in results
            if result.get("osm_type") == "relation"
            and result.get("type") == "administrative"
            and (result.get("geojson") or {}).get("type")
            in {"Polygon", "MultiPolygon"}
        ),
        None,
    )
    if boundary is None:
        raise RuntimeError(f"Boundary for {district} is not a polygon")

    return {
        "type": "Feature",
        "properties": {
            "district": district,
            "osm_id": boundary["osm_id"],
        },
        "geometry": boundary["geojson"],
    }


def main():
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    features = []

    for district, query in DISTRICT_QUERIES.items():
        features.append(fetch_polygon(session, district, query))
        print(f"Fetched {district}")
        time.sleep(1.1)

    collection = {
        "type": "FeatureCollection",
        "attribution": "© OpenStreetMap contributors",
        "features": features,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(collection, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Saved {len(features)} district boundaries to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
