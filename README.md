# Akcni Agent CZ – MVP

This version imports authorized CSV or JSON price catalogs into Supabase; it does not scrape supermarket websites yet.

## Setup
1. In Supabase SQL Editor, execute `schema.sql`.
2. In GitHub repository Settings > Secrets and variables > Actions, add **secrets** `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (Supabase Project Settings > API Keys; server-side secret only). Never commit keys.
3. Upload all project files preserving `.github/workflows/collect.yml`.
4. Install Python 3.11+: `pip install -r requirements.txt`.
5. Test validation: `python collector.py --dry-run`.
6. For a local demo database import: set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` environment variables, then `python collector.py --source data/sample.csv`.
7. To schedule **real** data, set GitHub Actions repository variable `CATALOG_SOURCE` to an authorized HTTPS CSV/JSON URL and `ALLOWED_SOURCE_HOSTS` to its exact hostname, e.g. `data.example.org`. If no source is configured, scheduled runs skip imports rather than inserting demo prices.
8. GitHub Actions > Collect prices > Run workflow to test. Schedule: 05:23 UTC daily (may be delayed).

CSV columns: retailer,store,sku,product_name,package,price_czk,price_type,source_url. `price_type`: regular/promotion/loyalty. JSON is an array of objects with the same keys.

The schema stores daily observations, not individual intraday price changes. Re-runs for the same day and SKU overwrite that day's observation. Historical changes on later days remain.

Caveats: only ingest data with permission; do not bypass website access controls. A public catalog may not reflect physical-store pricing. For production add source adapters, error alerts, store coverage reporting, source timestamp and offer validity, rate limits, and product matching.
