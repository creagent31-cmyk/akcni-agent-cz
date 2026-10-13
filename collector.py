"""Import authorized CSV/JSON catalog snapshots into Supabase."""
import argparse
import csv
import io
import json
import os
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse
import httpx

FIELDS = ('retailer','store','sku','product_name','package','price_czk','price_type','source_url')

def load_rows(source):
    if source.startswith(('https://','http://')):
        if not source.startswith('https://'):
            raise ValueError('Remote source must use HTTPS')
        allowed = [x.strip().lower() for x in os.getenv('ALLOWED_SOURCE_HOSTS','').split(',') if x.strip()]
        host = urlparse(source).hostname
        if not allowed or host not in allowed:
            raise ValueError('Host not on ALLOWED_SOURCE_HOSTS allowlist')
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            response = client.get(source)
            response.raise_for_status()
            if len(response.content) > 15_000_000:
                raise ValueError('Source too large')
            content = response.text
    else:
        content = Path(source).read_text(encoding='utf-8-sig')
    if source.lower().split('?')[0].endswith('.json'):
        rows = json.loads(content)
        if not isinstance(rows, list):
            raise ValueError('JSON must be an array')
        return rows
    return list(csv.DictReader(io.StringIO(content)))

def normalize(raw, observed_on):
    for field in ('retailer','sku','product_name','price_czk'):
        if not str(raw.get(field,'')).strip():
            raise ValueError(f'Missing {field}')
    try:
        price = Decimal(str(raw['price_czk']).replace(',','.').strip())
    except InvalidOperation as exc:
        raise ValueError('Invalid price') from exc
    if not price.is_finite() or price < 0:
        raise ValueError('Invalid price')
    price_type = str(raw.get('price_type') or 'regular').strip().lower()
    if price_type not in ('regular','promotion','loyalty'):
        raise ValueError('Invalid price_type')
    return {
        'retailer':str(raw['retailer']).strip(),
        'store':str(raw.get('store') or 'online').strip(),
        'sku':str(raw['sku']).strip(),
        'product_name':str(raw['product_name']).strip(),
        'package':str(raw.get('package') or '').strip(),
        'price_czk':str(price.quantize(Decimal('0.01'))),
        'price_type':price_type,
        'source_url':str(raw.get('source_url') or '').strip(),
        'observed_on':observed_on,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default=os.getenv('CATALOG_SOURCE','data/sample.csv'))
    parser.add_argument('--date', default=date.today().isoformat())
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    observed_on = date.fromisoformat(args.date).isoformat()
    raw_rows = load_rows(args.source)
    if not raw_rows:
        raise ValueError('No rows received: refusing to report success')
    rows = [normalize(r, observed_on) for r in raw_rows]
    # Last record wins for duplicate SKU/type/date within a source snapshot.
    rows = list({(r['retailer'],r['store'],r['sku'],r['price_type'],r['observed_on']):r for r in rows}.values())
    if args.dry_run:
        print(json.dumps(rows[:5],ensure_ascii=False,indent=2))
        print(f'Validated {len(rows)} records; no database writes')
        return
    url = os.environ['SUPABASE_URL']
    key = os.environ['SUPABASE_SERVICE_ROLE_KEY']
    from supabase import create_client
    db = create_client(url,key)
    for start in range(0,len(rows),200):
        db.table('price_observations').upsert(rows[start:start+200],on_conflict='retailer,store,sku,price_type,observed_on').execute()
    print(f'Imported {len(rows)} records from {args.source} on {observed_on}')

if __name__ == '__main__':
    main()
