# Dataset notes

`baku_housing_all_current.csv` is a snapshot of 62,627 public Baku sale
listings collected from `bina.az` through 2026-10-03. It contains 52,045
apartments and 10,582 houses after validation and duplicate removal.

`baku_housing_1000.csv` is the earlier 1,000-row snapshot from 2026-09-29.

The collector stores property characteristics and source URLs only. Seller
names, phone numbers, photos, and contact details are not collected. Before
running it again, obtain permission from the source owner and review the
current site terms; automated access is not enabled as a scheduled service.

The dataset contains asking prices, not confirmed transaction prices. Parking
is marked `unknown` unless it is explicitly mentioned in the listing text.
Repair quality is inferred from the listing's repair flag and description.
House floor counts are inferred from the description when available.
Coordinates represent a location or district centroid, not an exact property
position. Consequently, `distance_center_km` is also an approximate feature.

The large snapshot has 23 columns, including the source and update date, price,
property and building types, district, location, address, approximate location,
distance to central Baku, nearby metro indicator, home and land areas, rooms,
floors, repair quality, parking, title deed, and mortgage availability.

Run the collector again with:

```powershell
py scripts/collect_bina_listings.py --authorized-access --target 0 --workers 16 --checkpoint-every 500 --resume --output data/baku_housing_all_current.csv
```

`--target 0` scans the complete public sitemap. `--resume` continues from the
latest checkpoint. A location can be supplemented through the public search API
with `--location-id ID`; results are split by category and price to avoid the
search result pagination limit.
