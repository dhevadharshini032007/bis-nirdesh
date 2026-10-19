import json
import os
import re
import sys
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from google import genai


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
CHUNKS_PATH = PROJECT_ROOT / "data" / "chunks.json"
EMBEDDINGS_PATH = PROJECT_ROOT / "data" / "embeddings.json"
DOCUMENTS_PATH = PROJECT_ROOT / "data" / "documents.json"
COMMON_PRODUCT_KEYWORDS = {
    "water_is14543": ["water", "bottle", "jar", "pouch"],
    "helmet_is4151": ["helmet", "two wheeler", "motorcycle", "scooter", "visor", "chin strap"],
    "kettle_is302_2_15": ["kettle", "coffee maker", "cooker", "milk heater"],
    "lamp_is2596": ["bulb", "lamp", "miners cap lamp", "mining"],
}
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "how", "i", "in", "is", "it", "of", "on", "or", "that", "the",
    "this", "to", "was", "what", "when", "where", "which", "who", "why",
    "with", "you", "your",
}

load_dotenv(ENV_PATH, override=True, encoding="utf-8-sig")
API_KEY = os.getenv("GEMINI_API_KEY")
EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL")
if not API_KEY:
    raise ValueError(f"GEMINI_API_KEY is missing or empty; checked {ENV_PATH}")
if not EMBEDDING_MODEL:
    raise ValueError(f"GEMINI_EMBEDDING_MODEL is missing or empty; checked {ENV_PATH}")

CHUNKS = json.loads(CHUNKS_PATH.read_text(encoding="utf-8-sig"))
EMBEDDINGS = json.loads(EMBEDDINGS_PATH.read_text(encoding="utf-8-sig"))
DOCUMENTS = json.loads(DOCUMENTS_PATH.read_text(encoding="utf-8-sig"))
PRODUCT_KEYWORDS = {
    name: {
        keyword.lower()
        for keyword in (
            metadata.get("product_keywords", [])
            + COMMON_PRODUCT_KEYWORDS.get(name, [])
            + [name, name.split("_")[0]]
        )
    }
    for name, metadata in DOCUMENTS.items()
}
EMBEDDINGS_BY_ID = {item["chunk_id"]: item["embedding"] for item in EMBEDDINGS}
SEARCH_ITEMS = [
    (chunk, EMBEDDINGS_BY_ID[chunk["chunk_id"]])
    for chunk in CHUNKS
    if chunk["chunk_id"] in EMBEDDINGS_BY_ID
]
EMBEDDING_MATRIX = np.asarray([embedding for _, embedding in SEARCH_ITEMS], dtype=np.float32)
CLIENT = genai.Client(api_key=API_KEY)


def detect_document(query):
    normalized_query = query.lower()
    matched_documents = set()
    for name, keywords in PRODUCT_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in normalized_query:
                matched_documents.add(name)
                break
    return next(iter(matched_documents)) if len(matched_documents) == 1 else None


def search(query, top_k=5):
    if not query.strip() or top_k <= 0 or not SEARCH_ITEMS:
        return []

    response = CLIENT.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=query,
    )
    query_embedding = np.asarray(response.embeddings[0].values, dtype=np.float32)
    matrix_norms = np.linalg.norm(EMBEDDING_MATRIX, axis=1)
    query_norm = np.linalg.norm(query_embedding)
    denominator = matrix_norms * query_norm
    meaning_scores = np.divide(
        EMBEDDING_MATRIX @ query_embedding,
        denominator,
        out=np.zeros_like(matrix_norms),
        where=denominator != 0,
    )

    query_words = {
        word for word in re.findall(r"\w+", query.lower())
        if word not in STOP_WORDS
    }
    keyword_scores = []
    for chunk, _ in SEARCH_ITEMS:
        text_words = set(re.findall(r"\w+", chunk["text"].lower()))
        matched_words = len(query_words & text_words)
        keyword_scores.append(matched_words / len(query_words) if query_words else 0.0)

    final_scores = 0.8 * meaning_scores + 0.2 * np.asarray(keyword_scores)
    detected_document = detect_document(query)
    if detected_document:
        final_scores = final_scores + np.asarray([
            0.15 if Path(chunk["source_file"]).stem == detected_document else 0.0
            for chunk, _ in SEARCH_ITEMS
        ])
    ranked_indices = np.argsort(final_scores)[::-1][:top_k]
    fields = ("chunk_id", "is_number", "title", "page", "section_heading", "text")
    results = []
    for index in ranked_indices:
        chunk = SEARCH_ITEMS[int(index)][0]
        result = {field: chunk[field] for field in fields}
        result["score"] = float(final_scores[index])
        results.append(result)
    return results


def main():
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python -m retrieval.search "your question"')
    query = " ".join(sys.argv[1:])
    print(f"Detected document: {detect_document(query) or 'none'}\n")
    for index, result in enumerate(search(query, top_k=5), start=1):
        print(f"Result {index}")
        print(f"IS number: {result['is_number']}")
        print(f"Page: {result['page']}")
        print(f"Section: {result['section_heading']}")
        print(f"Score: {result['score']:.4f}")
        print(f"Text: {result['text'][:300]}\n")


if __name__ == "__main__":
    main()
