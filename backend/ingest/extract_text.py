from pathlib import Path

import fitz


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PDF_DIR = PROJECT_ROOT / "data"
TEXT_DIR = PROJECT_ROOT / "data_text"


def main():
    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    for pdf_path in sorted(PDF_DIR.glob("*.pdf")):
        document = fitz.open(pdf_path)
        pages = []
        for page_number, page in enumerate(document, start=1):
            pages.append(f"--- PAGE {page_number} ---\n{page.get_text()}")
        text = "\n".join(pages)
        output_path = TEXT_DIR / f"{pdf_path.stem}.txt"
        output_path.write_text(text, encoding="utf-8")
        print(f"{pdf_path.name}: {len(document)} pages, {len(text)} characters")
        document.close()


if __name__ == "__main__":
    main()
