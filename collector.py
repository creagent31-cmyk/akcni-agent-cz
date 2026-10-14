
"""Import CSV/JSON product prices into Supabase."""

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


REQUIRED_FIELDS = (
    "retailer",
    "sku",
    "product_name",
    "price_czk",
)

VALID_PRICE_TYPES = ("regular", "promotion", "loyalty")

OPTIONAL_FIELDS = (
    "source_type",
    "valid_from",
    "valid_to",
    "regular_price",
    "clubcard_price",
    "flyer_page",
)


def load_rows(source):
    if source.startswith(("https://", "http://")):
        if not source.startswith("https://"):
            raise ValueError("Remote source must use HTTPS")

        allowed = [
            x.strip().lower()
            for x in os.getenv("ALLOWED_SOURCE_HOSTS", "").split(",")
            if x.strip()
        ]

        host = urlparse(source).hostname

        if not allowed or host not in allowed:
            raise ValueError("Host not on ALLOWED_SOURCE_HOSTS allowlist")

        with httpx.Client(timeout=30, follow_redirects=False) as client:
            response = client.get(source)
            response.raise_for_status()

            if len(response.content) > 15_000_000:
                raise ValueError("Source too large")

            content = response.content.decode("utf-8-sig")

    else:
        content = Path(source).read_text(encoding="utf-8-sig")

    if source.lower().split("?")[0].endswith(".json"):
        rows = json.loads(content)

        if not isinstance(rows, list):
            raise ValueError("JSON must be an array")

        return rows

    # Remove empty lines and leading whitespace before header.
    content = content.lstrip("\ufeff\r\n \t")

    reader = csv.DictReader(io.StringIO(content))

    if not reader.fieldnames:
        raise ValueError("CSV is empty or missing header")

    reader.fieldnames = [
        name.strip().lstrip("\ufeff")
        for name in reader.fieldnames
    ]

    missing = [
        field for field in REQUIRED_FIELDS
        if field not in reader.fieldnames
    ]

    if missing:
        raise ValueError(
            f"Missing CSV columns: {missing}. "
            f"Found: {reader.fieldnames}"
        )

    rows = []

    for line_number, row in enumerate(reader, start=2):
        if None in row:
            raise ValueError(
                f"CSV line {line_number} has too many columns"
            )

        cleaned = {
            key: value.strip() if isinstance(value, str) else value
            for key, value in row.items()
        }

        if not any(cleaned.values()):
            continue

        rows.append(cleaned)

    return rows


def parse_price(value, field):
    try:
        price = Decimal(str(value).replace(",", ".").strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid {field}: {value}") from exc

    if not price.is_finite() or price < 0:
        raise ValueError(f"Invalid {field}: {value}")

    return str(price.quantize(Decimal("0.01")))


def normalize(raw, observed_on):
    for field in REQUIRED_FIELDS:
        if not str(raw.get(field) or "").strip():
            raise ValueError(
                f"Missing {field} in row: {raw}"
            )

    price_type = str(
        raw.get("price_type") or "regular"
    ).strip().lower()

    if price_type not in VALID_PRICE_TYPES:
        raise ValueError(
            f"Invalid price_type: {price_type}"
        )

    row = {
        "retailer": str(raw["retailer"]).strip(),
        "store": str(raw.get("store") or "online").strip(),
        "sku": str(raw["sku"]).strip(),
        "product_name": str(raw["product_name"]).strip(),
        "package": str(raw.get("package") or "").strip(),
        "price_czk": parse_price(
            raw["price_czk"], "price_czk"
        ),
        "price_type": price_type,
        "source_url": str(
            raw.get("source_url") or ""
        ).strip(),
        "observed_on": observed_on,
    }

    # Optional historical flyer fields.
    for field in OPTIONAL_FIELDS:
        value = raw.get(field)

        if value is None or str(value).strip() == "":
            continue

        if field in ("valid_from", "valid_to"):
            row[field] = date.fromisoformat(
                str(value).strip()
            ).isoformat()

        elif field in ("regular_price", "clubcard_price"):
            row[field] = parse_price(value, field)

        elif field == "flyer_page":
            row[field] = int(value)

        else:
            row[field] = str(value).strip()

    if (
        row.get("valid_from")
        and row.get("valid_to")
        and row["valid_from"] > row["valid_to"]
    ):
        raise ValueError("valid_from is after valid_to")

    return row


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--source",
        default=os.getenv(
            "CATALOG_SOURCE", "data/sample.csv"
        ),
    )

    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    args = parser.parse_args()

    observed_on = date.fromisoformat(
        args.date
    ).isoformat()

    raw_rows = load_rows(args.source)

    if not raw_rows:
        raise ValueError(
            "No rows received: refusing to report success"
        )

    print(f"Source: {args.source}")
    print(f"CSV columns: {list(raw_rows[0].keys())}")
    print(f"Rows loaded: {len(raw_rows)}")

    rows = [
        normalize(raw, observed_on)
        for raw in raw_rows
    ]

    # Avoid duplicates within the imported file.
    rows = list({
        (
            row["retailer"],
            row["store"],
            row["sku"],
            row["price_type"],
            row["observed_on"],
        ): row
        for row in rows
    }.values())

    if args.dry_run:
        print(
            json.dumps(
                rows[:5],
                ensure_ascii=False,
                indent=2,
            )
        )

        print(
            f"Validated {len(rows)} records; "
            "no database writes"
        )
        return

    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    from supabase import create_client

    db = create_client(url, key)

    for start in range(0, len(rows), 200):
        batch = rows[start:start + 200]

        db.table("price_observations").upsert(
            batch,
            on_conflict=(
                "retailer,store,sku,"
                "price_type,observed_on"
            ),
        ).execute()

    print(
        f"Imported {len(rows)} records "
        f"from {args.source} on {observed_on}"
    )


if __name__ == "__main__":
    main()
