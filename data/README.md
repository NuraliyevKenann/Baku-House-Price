# Dataset notes

`baku_housing_1000.csv` is a snapshot of 1,000 public Baku sale listings
collected from `bina.az` on 2026-09-29.

The collector uses the public sitemap and listing pages allowed by the site's
`robots.txt`. It stores property characteristics and source URLs only. Seller
names, phone numbers, photos, and contact details are not collected.

The dataset contains asking prices, not confirmed transaction prices. Parking
is marked `unknown` unless it is explicitly mentioned in the listing text.
Repair quality is inferred from the listing's repair flag and description.
House floor counts are inferred from the description when available.

Run the collector again with:

```powershell
py scripts/collect_bina_listings.py --target 1000
```
