import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEXT_DIR = PROJECT_ROOT / "data_text"
DATA_DIR = PROJECT_ROOT / "data"
PAGE_MARKER = re.compile(r"^--- PAGE (\d+) ---$")
HEADING_PATTERNS = (
    re.compile(r"^ANNEX\s*[-–]?\s*[A-Z](?:\s*[-–:]?\s*.*)?$", re.I),
    re.compile(r"^TABLE\s+\d+(?:\s*[-–:]?\s*.*)?$", re.I),
    re.compile(r"^[A-Z]-\d+(?:\.\d+)*(?:\s+.*)?$"),
)


def is_heading(line):
    value = line.strip()
    if not value:
        return False
    if any(pattern.fullmatch(value) for pattern in HEADING_PATTERNS):
        return True
    if len(value) >= 80 or value.endswith((".", "?", "!")):
        return False
    numbered_title = re.fullmatch(r"(\d+(?:\.\d+)*\.?)(?:\s+(\S.*))?", value)
    if not numbered_title:
        return False
    title = numbered_title.group(2) or ""
    starts_with_capital = bool(title) and title[0].isupper()
    is_annex_or_table = bool(re.match(r"^(?:ANNEX|TABLE)\b", title, re.I))
    if not title or (not starts_with_capital and not is_annex_or_table):
        return False
    if title and re.search(r"\b(?:shall|must|should|will|is|are|was|were|has|have|can|may)\b", title, re.I):
        return False
    return True


def split_pages(contents):
    page, lines = None, []
    for line in contents.splitlines():
        match = PAGE_MARKER.match(line.strip())
        if match:
            if page is not None:
                yield page, lines
            page, lines = int(match.group(1)), []
        elif page is not None:
            lines.append(line)
    if page is not None:
        yield page, lines


def split_sections(lines, previous_heading):
    heading, body = previous_heading, []
    sections = []
    for line in lines:
        value = line.strip()
        if not value:
            if body and body[-1] != "":
                body.append("")
        elif is_heading(value):
            if body:
                sections.append((heading, "\n".join(body).strip()))
            heading, body = value, [value]
        else:
            body.append(value)
    if body:
        sections.append((heading, "\n".join(body).strip()))
    return sections, heading


def split_long_paragraph(paragraph, limit):
    if len(paragraph) <= limit:
        return [paragraph]
    sentences = re.split(r"(?<=[.!?])\s+", paragraph)
    pieces, current = [], ""
    for sentence in sentences:
        if current and len(current) + 1 + len(sentence) > limit:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def split_text(text, limit=1500):
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    units = [unit for p in paragraphs for unit in split_long_paragraph(p, limit)]
    chunks, current = [], ""
    for unit in units:
        candidate = f"{current}\n\n{unit}" if current else unit
        if current and len(candidate) > limit:
            chunks.append(current)
            current = unit
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def tidy_table_text(text):
    lines = text.splitlines()
    tidied = []
    word_run = []
    one_word = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*[,:;]?", re.UNICODE)
    for line in lines:
        value = line.strip()
        if value and one_word.fullmatch(value):
            word_run.append(value)
        else:
            if len(word_run) > 1:
                tidied.append(" ".join(word_run))
            elif word_run:
                tidied.extend(word_run)
            word_run = []
            tidied.append(line)
    if len(word_run) > 1:
        tidied.append(" ".join(word_run))
    elif word_run:
        tidied.extend(word_run)
    return "\n".join(tidied)


def main():
    documents = json.loads((DATA_DIR / "documents.json").read_text(encoding="utf-8-sig"))
    chunks, counts = [], {}
    for text_path in sorted(TEXT_DIR.glob("*.txt")):
        key = text_path.stem
        if key not in documents:
            print(f"Skipping {text_path.name}: no metadata in documents.json")
            continue
        metadata = documents[key]
        file_chunks = []
        previous_heading = metadata["title"]
        contents = text_path.read_text(encoding="utf-8-sig")
        for page, lines in split_pages(contents):
            sections, previous_heading = split_sections(lines, previous_heading)
            page_chunks = []
            for heading, section_text in sections:
                for text in split_text(section_text):
                    page_chunks.append({
                        "chunk_id": "", "is_number": metadata["is_number"],
                        "title": metadata["title"], "doc_ref": metadata["doc_ref"],
                        "source_file": text_path.name, "page": page,
                        "section_heading": heading, "text": tidy_table_text(text),
                    })
            if page_chunks and file_chunks and not re.search(r"\.\s*$", file_chunks[-1]["text"]):
                previous_chunk = file_chunks[-1]
                continuing_chunk = page_chunks.pop(0)
                previous_chunk["text"] += "\n\n" + continuing_chunk["text"]
                previous_pages = previous_chunk.get("pages", [previous_chunk["page"]])
                previous_chunk["pages"] = list(dict.fromkeys(previous_pages + [page]))
            file_chunks.extend(page_chunks)
        merged_chunks = []
        for chunk in file_chunks:
            if len(chunk["text"]) < 200 and merged_chunks:
                previous_chunk = merged_chunks[-1]
                previous_chunk["text"] += "\n\n" + chunk["text"]
                previous_pages = previous_chunk.get("pages", [previous_chunk["page"]])
                chunk_pages = chunk.get("pages", [chunk["page"]])
                combined_pages = list(dict.fromkeys(previous_pages + chunk_pages))
                if len(combined_pages) > 1:
                    previous_chunk["pages"] = combined_pages
            else:
                merged_chunks.append(chunk)
        file_chunks = merged_chunks
        for index, chunk in enumerate(file_chunks, start=1):
            chunk["chunk_id"] = f"{key}_{index:04d}"
            keywords = metadata["product_keywords"][:3]
            previous_context = file_chunks[index - 2]["text"][-200:] if index > 1 else ""
            chunk["embed_text"] = (
                f"Previous context: {previous_context}\n\n"
                f"Document: {metadata['is_number']} - {metadata['title']}. "
                f"Products: {', '.join(keywords)}. Section: {chunk['section_heading']}. "
                f"Page {chunk['page']}.\n\n{chunk['text']}"
            )
        chunks.extend(file_chunks)
        counts[key] = len(file_chunks)
    (DATA_DIR / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\nSample chunks:")
    for chunk in chunks[:3]:
        print(json.dumps(chunk, ensure_ascii=False, indent=2))
    print("\nChunk counts:")
    for key, count in counts.items():
        print(f"{key}: {count} chunks")


if __name__ == "__main__":
    main()


