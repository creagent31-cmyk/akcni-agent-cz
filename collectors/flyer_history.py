
"""Větev 2: zpracování historických akčních letáků."""

from pathlib import Path

def main():
    folder = Path("data/flyers")
    folder.mkdir(parents=True, exist_ok=True)

    pdf_files = list(folder.glob("*.pdf"))

    print(f"Nalezeno historických letáků: {len(pdf_files)}")

    for pdf in pdf_files:
        print(f"Leták ke zpracování: {pdf.name}")

if __name__ == "__main__":
    main()
