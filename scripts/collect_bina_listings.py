import argparse
import csv
import json
import math
import re
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


SITEMAP_INDEX = "https://bina.azstatic.com/uploads/sitemaps/sitemap_items.xml"
GRAPHQL_URL = "https://bina.az/graphql"
USER_AGENT = "BakuHousePriceResearch/1.0 (public listing data; no contact data)"
BAKU_CENTER = (40.3667, 49.8352)

DISTRICT_BY_SLUG = {
    "abseron": "Absheron",
    "bineqedi": "Binagadi",
    "qaradag": "Garadagh",
    "xetai": "Khatai",
    "xezer": "Khazar",
    "nerimanov": "Narimanov",
    "nesimi": "Nasimi",
    "nizami": "Nizami",
    "pirallahi": "Pirallahi",
    "sabuncu": "Sabunchu",
    "sebail": "Sabail",
    "suraxani": "Surakhani",
    "yasamal": "Yasamal",
}

EXCELLENT_REPAIR_WORDS = (
    "əla təmir",
    "ela temir",
    "ideal təmir",
    "bahalı təmir",
    "yüksək keyfiyyət",
    "lux təmir",
    "lüks təmir",
)
AVERAGE_REPAIR_WORDS = ("orta təmir", "normal təmir", "qismən təmir")
PARKING_WORDS = ("parking", "parkovka", "qaraj", "dayanacaq")
PARTIAL_PRICE_WORDS = (
    "ilkin \u00f6d\u0259ni\u015f",
    "ilk \u00f6d\u0259ni\u015f",
    "ayl\u0131q \u00f6d\u0259ni\u015f",
    "qalan borc",
    "kredit qal\u0131\u011f\u0131",
)

CSV_COLUMNS = [
    "listing_id",
    "source_url",
    "updated_at",
    "price_azn",
    "property_type",
    "building_type",
    "district",
    "location_name",
    "address",
    "location_centroid_latitude",
    "location_centroid_longitude",
    "coordinate_level",
    "distance_center_km",
    "metro_near",
    "area_m2",
    "land_area_sot",
    "rooms",
    "floor",
    "total_floors",
    "repair_quality",
    "has_parking",
    "has_bill_of_sale",
    "has_mortgage",
]

THREAD_LOCAL = threading.local()


def build_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def thread_session():
    if not hasattr(THREAD_LOCAL, "session"):
        THREAD_LOCAL.session = build_session()
    return THREAD_LOCAL.session


def fetch_text(session, url, timeout=25):
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def sitemap_entries(session):
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    index_root = ET.fromstring(fetch_text(session, SITEMAP_INDEX))
    sitemap_urls = [
        node.text for node in index_root.findall(".//sm:loc", namespace)
    ]

    entries = []
    for sitemap_url in sitemap_urls:
        root = ET.fromstring(fetch_text(session, sitemap_url, timeout=60))
        for url_node in root.findall("sm:url", namespace):
            location = url_node.findtext("sm:loc", default="", namespaces=namespace)
            modified = url_node.findtext(
                "sm:lastmod", default="", namespaces=namespace
            )
            if location.startswith("https://bina.az/items/"):
                entries.append((modified, location))

    entries.sort(reverse=True)
    return [url for _, url in entries]


def location_entries(session, location_id):
    query = """
    query SearchItems(
      $first: Int
      $filter: ItemFilter
      $sort: ItemConnectionSort!
      $cursor: String
    ) {
      itemsConnection(
        first: $first
        after: $cursor
        filter: $filter
        sort: $sort
      ) {
        pageInfo { hasNextPage endCursor }
        edges { node { id } }
      }
    }
    """
    urls = []
    price_bands = (
        (20000, 99999),
        (100000, 149999),
        (150000, 199999),
        (200000, 249999),
        (250000, 299999),
        (300000, 499999),
        (500000, 999999),
        (1000000, 5000000),
    )
    for category_id in ("2", "3", "5"):
        for price_from, price_to in price_bands:
            cursor = None
            while True:
                response = session.post(
                    GRAPHQL_URL,
                    json={
                        "operationName": "SearchItems",
                        "query": query,
                        "variables": {
                            "first": 100,
                            "filter": {
                                "cityId": "1",
                                "categoryId": category_id,
                                "locationIds": [str(location_id)],
                                "leased": False,
                                "priceFrom": price_from,
                                "priceTo": price_to,
                            },
                            "sort": "BUMPED_AT_DESC",
                            "cursor": cursor,
                        },
                    },
                    timeout=30,
                )
                response.raise_for_status()
                connection = response.json()["data"]["itemsConnection"]
                urls.extend(
                    f"https://bina.az/items/{edge['node']['id']}"
                    for edge in connection["edges"]
                )
                page_info = connection["pageInfo"]
                if not page_info["hasNextPage"]:
                    break
                cursor = page_info["endCursor"]
    return list(dict.fromkeys(urls))


def extract_next_data(html):
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    if not match:
        return None
    return json.loads(match.group(1))


def normalize_text(value):
    return (value or "").strip().lower()


def is_sale_listing(item):
    return any(
        breadcrumb.get("path") == "/alqi-satqi"
        for breadcrumb in item.get("breadcrumbs") or []
    )


def has_partial_price(description):
    text = normalize_text(description)
    return any(word in text for word in PARTIAL_PRICE_WORDS)


def land_area_in_sot(land_area):
    if not land_area or land_area.get("value") is None:
        return None
    value = float(land_area["value"])
    units = normalize_text(land_area.get("units"))
    if units in {"sot", "sotka"}:
        return value
    if units in {"m\u00b2", "m2"}:
        return value / 100
    if units in {"ha", "hektar"}:
        return value * 100
    return None


def location_coordinates(page_props, location, nearest_locations):
    candidates = [
        {
            "path": (location or {}).get("path"),
            "id": (location or {}).get("id"),
            "level": "location",
        }
    ]
    candidates.extend(
        {
            "path": nearest.get("path"),
            "id": nearest.get("id"),
            "level": "location" if index == 0 else "district",
        }
        for index, nearest in enumerate(reversed(nearest_locations or []))
    )
    state = page_props.get("apolloState", {})
    for candidate in candidates:
        for key, value in state.items():
            if not isinstance(value, dict) or value.get("__typename") != "Location":
                continue
            same_path = candidate["path"] and value.get("path") == candidate["path"]
            same_id = candidate["id"] and (
                str(value.get("id")) == str(candidate["id"])
                or key == f"Location:{candidate['id']}"
            )
            if (
                (same_path or same_id)
                and value.get("latitude") is not None
                and value.get("longitude") is not None
            ):
                return (
                    float(value["latitude"]),
                    float(value["longitude"]),
                    candidate["level"],
                )
    return None, None, "unavailable"


def distance_km(latitude, longitude):
    if latitude is None or longitude is None:
        return None
    earth_radius_km = 6371.0088
    center_latitude, center_longitude = BAKU_CENTER
    latitude_1 = math.radians(center_latitude)
    latitude_2 = math.radians(latitude)
    delta_latitude = math.radians(latitude - center_latitude)
    delta_longitude = math.radians(longitude - center_longitude)
    haversine = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(latitude_1)
        * math.cos(latitude_2)
        * math.sin(delta_longitude / 2) ** 2
    )
    return round(
        2 * earth_radius_km * math.asin(math.sqrt(haversine)), 2
    )


def property_kind(category):
    slug = normalize_text(category.get("slug"))
    name = normalize_text(category.get("name"))
    if "menziller" in slug:
        building_type = "new_building" if "yeni" in name else "old_building"
        return "apartment", building_type
    if "heyet" in slug or "bağ evi" in name or "bag evi" in name:
        return "house", "house"
    return None, None


def extract_district(nearest_locations):
    for location in nearest_locations or []:
        parts = location.get("path", "").strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "baki":
            district = DISTRICT_BY_SLUG.get(parts[1])
            if district:
                return district
    return None


def has_nearby_metro(nearest_locations):
    for location in nearest_locations or []:
        name = normalize_text(location.get("fullName"))
        if name.endswith(" m.") or " metrosu" in name:
            return "yes"
    return "no"


def repair_quality(has_repair, description):
    text = normalize_text(description)
    if not has_repair:
        return "needs_repair"
    if any(word in text for word in EXCELLENT_REPAIR_WORDS):
        return "excellent"
    if any(word in text for word in AVERAGE_REPAIR_WORDS):
        return "average"
    return "good"


def parking_status(description):
    text = normalize_text(description)
    return "yes" if any(word in text for word in PARKING_WORDS) else "unknown"


def infer_house_floors(description):
    text = normalize_text(description)
    patterns = (
        r"(\d+)\s*[- ]?mərtəbəli",
        r"(\d+)\s*[- ]?mertebeli",
        r"(\d+)\s*mərtəbədən",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return max(1, min(int(match.group(1)), 5))
    return 1


def parse_listing(url, session):
    try:
        html = fetch_text(session, url)
        payload = extract_next_data(html)
        if not payload:
            return None

        page_props = payload.get("props", {}).get("pageProps", {})
        item = page_props.get("currentItemData")
        if not item or item.get("isLeased") or item.get("state") != "PUBLISHED":
            return None
        if not is_sale_listing(item):
            return None
        if str(item.get("city", {}).get("id")) != "1":
            return None

        property_type, building_type = property_kind(item.get("category", {}))
        if not property_type:
            return None

        district = extract_district(item.get("nearestLocations"))
        price = item.get("price", {}).get("total")
        area = item.get("area", {}).get("value")
        rooms = item.get("rooms")
        if not district or not price or not area or not rooms:
            return None
        if price < 20000 or price > 5000000 or area < 20 or area > 1500:
            return None

        description = item.get("description") or ""
        if has_partial_price(description):
            return None
        if property_type == "house":
            floor = 1
            total_floors = infer_house_floors(description)
        else:
            floor = item.get("floor")
            total_floors = item.get("floors")
            if not floor or not total_floors or floor > total_floors:
                return None

        location = item.get("location") or {}
        latitude, longitude, coordinate_level = location_coordinates(
            page_props,
            location,
            item.get("nearestLocations"),
        )
        return {
            "listing_id": str(item.get("id")),
            "source_url": url,
            "updated_at": item.get("updatedAt") or "",
            "price_azn": int(price),
            "property_type": property_type,
            "building_type": building_type,
            "district": district,
            "location_name": (location.get("fullName") or district).strip(),
            "address": (item.get("address") or "").strip(),
            "location_centroid_latitude": latitude,
            "location_centroid_longitude": longitude,
            "coordinate_level": coordinate_level,
            "distance_center_km": distance_km(latitude, longitude),
            "metro_near": has_nearby_metro(item.get("nearestLocations")),
            "area_m2": float(area),
            "land_area_sot": land_area_in_sot(item.get("landArea")),
            "rooms": int(rooms),
            "floor": int(floor),
            "total_floors": int(total_floors),
            "repair_quality": repair_quality(item.get("hasRepair"), description),
            "has_parking": parking_status(description),
            "has_bill_of_sale": "yes" if item.get("hasBillOfSale") else "no",
            "has_mortgage": "yes" if item.get("hasMortgage") else "no",
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, requests.RequestException):
        return None


def parse_listing_in_worker(url):
    return parse_listing(url, thread_session())


def property_fingerprint(row):
    return tuple(
        str(row[column])
        for column in (
            "district",
            "location_name",
            "price_azn",
            "area_m2",
            "rooms",
            "floor",
            "total_floors",
        )
    )


def read_existing_rows(output_path):
    if not output_path.exists():
        return []
    with output_path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def collect(target, workers, output_path, checkpoint_every, resume, location_id):
    session = build_session()
    urls = (
        location_entries(session, location_id)
        if location_id
        else sitemap_entries(session)
    )

    rows = read_existing_rows(output_path) if resume else []
    seen_ids = {str(row["listing_id"]) for row in rows}
    seen_properties = {property_fingerprint(row) for row in rows}
    batch_size = max(workers * 5, 20)
    if seen_ids and not location_id:
        saved_positions = [
            index
            for index, url in enumerate(urls)
            if url.rsplit("/", 1)[-1] in seen_ids
        ]
        if saved_positions:
            resume_at = max(0, max(saved_positions) - batch_size)
            urls = urls[resume_at:]
    checked = 0

    if rows:
        print(f"Resuming with {len(rows)} saved listings")

    for start in range(0, len(urls), batch_size):
        if target and len(rows) >= target:
            break

        batch = urls[start : start + batch_size]
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(parse_listing_in_worker, url): url
                for url in batch
            }
            for future in as_completed(futures):
                checked += 1
                row = future.result()
                fingerprint = property_fingerprint(row) if row else None
                if (
                    row
                    and row["listing_id"] not in seen_ids
                    and fingerprint not in seen_properties
                ):
                    seen_ids.add(row["listing_id"])
                    seen_properties.add(fingerprint)
                    rows.append(row)
                    if len(rows) % 100 == 0:
                        target_text = str(target) if target else "all"
                        print(
                            f"Collected {len(rows)}/{target_text} "
                            f"from {checked} checked URLs"
                        )
                    if checkpoint_every and len(rows) % checkpoint_every == 0:
                        write_csv(rows, output_path)
                if target and len(rows) >= target:
                    break

        time.sleep(0.15)

    return (rows[:target] if target else rows), checked


def write_csv(rows, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Collect public Baku sale listings without seller contact data."
    )
    parser.add_argument("--target", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--checkpoint-every", type=int, default=500)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--location-id", type=int)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/baku_housing_current.csv"),
    )
    args = parser.parse_args()

    rows, checked = collect(
        args.target,
        args.workers,
        args.output,
        args.checkpoint_every,
        args.resume,
        args.location_id,
    )
    if args.target and len(rows) < args.target:
        raise RuntimeError(
            f"Only {len(rows)} valid listings collected after checking {checked} URLs."
        )

    write_csv(rows, args.output)
    print(f"Saved {len(rows)} listings to {args.output}")


if __name__ == "__main__":
    main()
