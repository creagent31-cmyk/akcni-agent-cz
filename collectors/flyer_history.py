
"""Find price candidates in PDF supermarket flyers.

Outputs:
- flyer_candidates.csv: possible prices and nearby text
- flyer_text_blocks.csv: all extracted text blocks

No automatic Supabase writes.
"""

import argparse
import csv
import re
from pathlib import Path

import fitz


PRICE_RE = re.compile(
    r"(?<!\d)(\d{1,4}[,.]\d{2})(?!\d)"
)


def clean(text):
    return " ".join(text.split()).strip()


def extract(pdf_path, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)

    candidates_path = output_dir / "flyer_candidates.csv"
    blocks_path = output_dir / "flyer_text_blocks.csv"

    all_blocks = []
    candidates = []

    with fitz.open(pdf_path) as document:
        for page_number, page in enumerate(document, start=1):
            page_blocks = []

            for block in page.get_text("blocks"):
                x0, y0, x1, y1, content, *_ = block
                content = clean(content)

                if not content:
                    continue

                item = {
                    "source_file": pdf_path.name,
                    "page": page_number,
                    "x0": round(x0, 1),
                    "y0": round(y0, 1),
                    "x1": round(x1, 1),
                    "y1": round(y1, 1),
                    "text": content,
                }

                page_blocks.append(item)
                all_blocks.append(item)

            for block in page_blocks:
                prices = PRICE_RE.findall(block["text"])

                if not prices:
                    continue

                # Find nearby text as a review hint.
                nearby = []

                for other in page_blocks:
                    if other is block:
                        continue

                    dx = max(
                        0,
                        other["x0"] - block["x1"],
                        block["x0"] - other["x1"],
                    )

                    dy = max(
                        0,
                        other["y0"] - block["y1"],
                        block["y0"] - other["y1"],
                    )

                    distance = (dx * dx + dy * dy) ** 0.5

                    if distance <= 110:
                        nearby.append((distance, other["text"]))

                nearby.sort(key=lambda item: item[0])

                context = " | ".join(
                    text for _, text in nearby[:5]
                )

                for price in prices:
                    candidates.append({
                        "source_file": pdf_path.name,
                        "page": page_number,
                        "price_candidate": price.replace(",", "."),
                        "price_text": block["text"],
                        "nearby_text": context,
                        "x0": block["x0"],
                        "y0": block["y0"],
                        "review_status": "needs_review",
                    })

    block_fields = [
        "source_file", "page",
        "x0", "y0", "x1", "y1", "text",
    ]

    candidate_fields = [
        "source_file", "page",
        "price_candidate", "price_text",
        "nearby_text", "x0", "y0",
        "review_status",
    ]

    with blocks_path.open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=block_fields
        )
        writer.writeheader()
        writer.writerows(all_blocks)

    with candidates_path.open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=candidate_fields
        )
        writer.writeheader()
        writer.writerows(candidates)

    print(f"PDF pages processed successfully")
    print(f"Text blocks: {len(all_blocks)}")
    print(f"Price candidates: {len(candidates)}")
    print(f"Candidates saved: {candidates_path}")
    print(f"Text saved: {blocks_path}")
    print("All candidates require review.")
    print("No data imported into Supabase.")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "pdf",
        type=Path,
        help="Path to PDF flyer",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/output"),
    )

    args = parser.parse_args()

    if not args.pdf.is_file():
        parser.error(f"PDF not found: {args.pdf}")

    extract(args.pdf, args.output_dir)


if __name__ == "__main__":
    main()
