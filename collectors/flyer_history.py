"""Extract reviewable text blocks from supermarket flyer PDFs.

Usage: python collectors/flyer_history.py path/to/flyer.pdf
Dependency: pip install pymupdf
Output: flyer_candidates.csv (page, coordinates, text). Prices must be paired
with products and validated before importing into price_observations.
"""
import argparse
import csv
from pathlib import Path
import fitz


def extract(pdf_path: Path, output: Path) -> int:
    count = 0
    with fitz.open(pdf_path) as document, output.open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.writer(handle)
        writer.writerow(['source_file', 'page', 'x0', 'y0', 'x1', 'y1', 'text'])
        for page_num, page in enumerate(document, start=1):
            for block in page.get_text('blocks'):
                x0, y0, x1, y1, content, *_ = block
                content = ' '.join(content.split())
                if not content:
                    continue
                writer.writerow([pdf_path.name, page_num, round(x0, 1), round(y0, 1),
                                 round(x1, 1), round(y1, 1), content])
                count += 1
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('pdf', type=Path)
    parser.add_argument('--output', type=Path, default=Path('flyer_candidates.csv'))
    args = parser.parse_args()
    if not args.pdf.is_file():
        parser.error(f'PDF not found: {args.pdf}')
    count = extract(args.pdf, args.output)
    print(f'Extracted {count} text blocks into {args.output}. Review before database import.')


if __name__ == '__main__':
    main()
