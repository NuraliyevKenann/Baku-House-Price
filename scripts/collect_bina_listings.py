import argparse
import csv
import json
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
USER_AGENT = "BakuHousePriceResearch/1.0 (public listing data; no contact data)"

DISTRICT_BY_SLUG = {
    "abseron": "Absheron",
    "binegedi": "Binagadi",
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

CSV_COLUMNS = [
    "listing_id",
    "source_url",
    "updated_at",
    "price_azn",
    "property_type",
    "building_type",
    "district",
    "location_name",
    "metro_near",
    "area_m2",
    "rooms",
    "floor",
    "total_floors",
    "repair_quality",
    "has_parking",
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
        if property_type == "house":
            floor = 1
            total_floors = infer_house_floors(description)
        else:
            floor = item.get("floor")
            total_floors = item.get("floors")
            if not floor or not total_floors or floor > total_floors:
                return None

        location = item.get("location") or {}
        return {
            "listing_id": str(item.get("id")),
            "source_url": url,
            "updated_at": item.get("updatedAt") or "",
            "price_azn": int(price),
            "property_type": property_type,
            "building_type": building_type,
            "district": district,
            "location_name": (location.get("fullName") or district).strip(),
            "metro_near": has_nearby_metro(item.get("nearestLocations")),
            "area_m2": float(area),
            "rooms": int(rooms),
            "floor": int(floor),
            "total_floors": int(total_floors),
            "repair_quality": repair_quality(item.get("hasRepair"), description),
            "has_parking": parking_status(description),
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, requests.RequestException):
        return None


def parse_listing_in_worker(url):
    return parse_listing(url, thread_session())


def collect(target, workers):
    session = build_session()
    urls = sitemap_entries(session)

    rows = []
    seen_ids = set()
    seen_properties = set()
    checked = 0
    batch_size = max(workers * 5, 20)

    for start in range(0, len(urls), batch_size):
        if len(rows) >= target:
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
                if row:
                    fingerprint = (
                        row["district"],
                        row["location_name"],
                        row["price_azn"],
                        row["area_m2"],
                        row["rooms"],
                        row["floor"],
                        row["total_floors"],
                    )
                if (
                    row
                    and row["listing_id"] not in seen_ids
                    and fingerprint not in seen_properties
                ):
                    seen_ids.add(row["listing_id"])
                    seen_properties.add(fingerprint)
                    rows.append(row)
                    if len(rows) % 100 == 0:
                        print(f"Collected {len(rows)}/{target} from {checked} checked URLs")
                if len(rows) >= target:
                    break

        time.sleep(0.15)

    return rows[:target], checked


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
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/baku_housing_1000.csv"),
    )
    args = parser.parse_args()

    rows, checked = collect(args.target, args.workers)
    if len(rows) < args.target:
        raise RuntimeError(
            f"Only {len(rows)} valid listings collected after checking {checked} URLs."
        )

    write_csv(rows, args.output)
    print(f"Saved {len(rows)} listings to {args.output}")


if __name__ == "__main__":
    main()
