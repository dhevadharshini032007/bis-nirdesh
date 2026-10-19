import difflib
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai

from retrieval.search import detect_document, search


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
FALLBACK_ANSWER = "I couldn't find a verifiable answer in the provided BIS documents."


def _normalize_text(text):
    text = text.lower()
    text = re.sub(r"-[ \t]*\r?\n[ \t]*", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _fuzzy_match_position(quote, chunk_text):
    normalized_quote = _normalize_text(quote)
    normalized_chunk = _normalize_text(chunk_text)
    if not normalized_quote or not normalized_chunk:
        return 0.0, None

    matcher = difflib.SequenceMatcher(None, normalized_quote, normalized_chunk, autojunk=False)
    tolerance = max(1, int(len(normalized_quote) * 0.1))
    best_ratio, best_start = 0.0, None
    for block in matcher.get_matching_blocks():
        if block.size == 0:
            continue
        aligned_start = max(0, block.b - block.a)
        for start in range(max(0, aligned_start - tolerance), min(len(normalized_chunk), aligned_start + tolerance + 1)):
            for length in range(max(1, len(normalized_quote) - tolerance), len(normalized_quote) + tolerance + 1):
                candidate = normalized_chunk[start:start + length]
                if not candidate:
                    continue
                ratio = difflib.SequenceMatcher(None, normalized_quote, candidate, autojunk=False).ratio()
                if ratio > best_ratio:
                    best_ratio, best_start = ratio, start
    return best_ratio, best_start


def verify_quote(quote, chunk_text):
    normalized_quote = _normalize_text(quote)
    normalized_chunk = _normalize_text(chunk_text)
    if normalized_quote and normalized_quote in normalized_chunk:
        return {"verified": True, "match_type": "exact"}
    ratio, _ = _fuzzy_match_position(quote, chunk_text)
    if ratio >= 0.9:
        return {"verified": True, "match_type": "fuzzy"}
    return {"verified": False, "match_type": "none"}


def find_clause_ref(chunk_text, quote):
    normalized_chunk = _normalize_text(chunk_text)
    normalized_quote = _normalize_text(quote)
    quote_position = normalized_chunk.find(normalized_quote) if normalized_quote else -1
    if quote_position < 0:
        _, quote_position = _fuzzy_match_position(quote, chunk_text)
    if quote_position is None:
        quote_position = len(normalized_chunk)

    clause_pattern = re.compile(
        r"\bClause\s+\d+(?:\.\d+)*\b|\bANNEX\s*[-–]?\s*[A-Z0-9]+\b|"
        r"\b[A-Z]-\d+(?:\.\d+)*\b|\b\d+(?:\.\d+){1,}\b",
        re.I,
    )
    prefix = normalized_chunk[:quote_position]
    matches = list(clause_pattern.finditer(prefix))
    if not matches:
        return None
    return max(matches, key=lambda match: match.start()).group(0)


def _parse_response(response_text):
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[^\r\n]*(?:\r?\n)?", "", cleaned, count=1)
        cleaned = re.sub(r"\s*```$", "", cleaned, count=1)
    data = json.loads(cleaned)
    if not isinstance(data, dict) or not isinstance(data.get("no_evidence"), bool):
        raise ValueError("JSON must contain a boolean no_evidence field")
    points = data.get("points")
    if not isinstance(points, list):
        raise ValueError("JSON must contain a points list")
    for point in points:
        if (
            not isinstance(point, dict)
            or not isinstance(point.get("statement"), str)
            or not isinstance(point.get("source"), int)
            or not isinstance(point.get("quote"), str)
        ):
            raise ValueError("Each point must contain statement, integer source, and quote fields")
    return data


def _fallback_response(detected_document, sources=None):
    return {
        "answer": FALLBACK_ANSWER,
        "points": [],
        "verification_summary": "0 of 0 statements verified",
        "evidence_found": False,
        "detected_document": detected_document,
        "sources": sources or [],
    }


def answer_question(query, language="English", user_type=None, top_k=5):
    detected_document = detect_document(query) or "none"
    retrieved = search(query, top_k=top_k)
    sources = [
        {
            "source": index,
            "is_number": chunk["is_number"],
            "title": chunk["title"],
            "page": chunk["page"],
            "section_heading": chunk["section_heading"],
        }
        for index, chunk in enumerate(retrieved, start=1)
    ]
    if not retrieved:
        return _fallback_response(detected_document, sources)

    load_dotenv(ENV_PATH, override=True, encoding="utf-8-sig")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(f"GEMINI_API_KEY is missing or empty; checked {ENV_PATH}")
    client = genai.Client(api_key=api_key)
    evidence = "\n\n".join(
        f"[{index}] IS: {chunk['is_number']} | Title: {chunk['title']} | Page: {chunk['page']} | "
        f"Section: {chunk['section_heading']}\n{chunk['text']}"
        for index, chunk in enumerate(retrieved, start=1)
    )
    user_guidance = {
        "msme": "For an MSME, explain practical steps, testing costs, and documents needed, using only the supplied chunks.",
        "manufacturer": "For a manufacturer, explain practical steps, testing costs, and documents needed, using only the supplied chunks.",
        "consumer": "For a consumer, use plain language and focus on what the label and ISI mark mean for them, using only the supplied chunks.",
        "student": "For a student, briefly explain terms and give a simple example, using only the supplied chunks.",
    }.get(user_type)
    prompt = (
        "Answer using only the supplied BIS chunks. Return ONLY valid JSON in exactly this shape: "
        '{"no_evidence": false, "points": [{"statement": "...", "source": 1, '
        '"quote": "exact words copied from chunk [1], max 200 characters"}]}. '
        'The quote must be copied word for word from the cited chunk. If the chunks do not contain '
        'the answer, return {"no_evidence": true, "points": []}. Do not add markdown or prose outside JSON. '
        f"Write statements in {language}; keep quotes exactly as they appear in the original English text.\n"
        f"{user_guidance + chr(10) if user_guidance else ''}"
        f"Question: {query}\n\nChunks:\n{evidence}"
    )

    parsed = None
    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
                contents=prompt,
            )
            parsed = _parse_response(response.text or "")
            break
        except (json.JSONDecodeError, ValueError, TypeError):
            if attempt == 1:
                raise ValueError("Could not parse Gemini's JSON response after two attempts.")

    if parsed["no_evidence"] or not parsed["points"]:
        return _fallback_response(detected_document, sources)

    verified_points = []
    for point in parsed["points"]:
        source_index = point["source"]
        if source_index < 1 or source_index > len(retrieved):
            verified_points.append({
                "statement": point["statement"],
                "source": source_index,
                "is_number": None,
                "title": None,
                "page": None,
                "clause_ref": None,
                "quote": point["quote"],
                "verified": False,
                "match_type": "none",
            })
            continue
        chunk = retrieved[source_index - 1]
        verification = (
            {"verified": False, "match_type": "none"}
            if len(point["quote"]) > 200
            else verify_quote(point["quote"], chunk["text"])
        )
        verified_points.append({
            "statement": point["statement"],
            "source": source_index,
            "is_number": chunk["is_number"],
            "title": chunk["title"],
            "page": chunk["page"],
            "clause_ref": find_clause_ref(chunk["text"], point["quote"]),
            "quote": point["quote"],
            "verified": verification["verified"],
            "match_type": verification["match_type"],
        })

    verified = [point for point in verified_points if point["verified"]]
    if not verified:
        answer = FALLBACK_ANSWER
    else:
        answer = "\n".join(f"{index}. {point['statement']}" for index, point in enumerate(verified, start=1))
    return {
        "answer": answer,
        "points": verified_points,
        "verification_summary": f"{len(verified)} of {len(verified_points)} statements verified",
        "evidence_found": bool(verified),
        "detected_document": detected_document,
        "sources": sources,
    }
