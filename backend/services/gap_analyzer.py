import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai

from retrieval.search import CHUNKS, DOCUMENTS, detect_document, search
from services.assistant import find_clause_ref, verify_quote


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
TOPIC_SEARCHES = (
    "sampling and grouping guidelines",
    "declarations required",
    "test equipment and tests",
    "marking and labelling",
    "certification process and documents",
)


def _parse_response(response_text):
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[^\r\n]*(?:\r?\n)?", "", cleaned, count=1)
        cleaned = re.sub(r"\s*```$", "", cleaned, count=1)
    data = json.loads(cleaned)
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ValueError("Gemini response must contain an items list")
    for item in data["items"]:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("requirement"), str)
            or item.get("status") not in {"provided", "missing", "unclear"}
            or not isinstance(item.get("reason"), str)
            or not isinstance(item.get("source"), int)
            or not isinstance(item.get("quote"), str)
        ):
            raise ValueError("Gemini response contains an invalid item")
    return data


def _retrieve_for_document(document_name):
    metadata = DOCUMENTS[document_name]
    product_name = metadata["title"]
    candidates = {}
    source_stems = {
        chunk["chunk_id"]: Path(chunk["source_file"]).stem
        for chunk in CHUNKS
    }
    for topic in TOPIC_SEARCHES:
        results = search(f"{product_name}: {topic}", top_k=len(CHUNKS))
        for chunk in results:
            if source_stems.get(chunk["chunk_id"]) == document_name:
                previous = candidates.get(chunk["chunk_id"])
                if previous is None or chunk["score"] > previous["score"]:
                    candidates[chunk["chunk_id"]] = chunk
    ranked = sorted(candidates.values(), key=lambda chunk: chunk["score"], reverse=True)
    return ranked[:10]


def analyze_product(description, language="English", user_type=None):
    detected_document = detect_document(description)
    if not detected_document:
        return {"error": "Please mention which product you mean (helmet, electric kettle, packaged drinking water, or lamp)."}

    metadata = DOCUMENTS[detected_document]
    retrieved = _retrieve_for_document(detected_document)
    if not retrieved:
        raise ValueError("No supporting BIS product manual chunks were found for this product.")

    load_dotenv(ENV_PATH, override=True, encoding="utf-8-sig")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(f"GEMINI_API_KEY is missing or empty; checked {ENV_PATH}")
    client = genai.Client(api_key=api_key)
    chunks_by_source = {index: chunk for index, chunk in enumerate(retrieved, start=1)}
    evidence = "\n\n".join(
        f"[{index}] IS: {chunk['is_number']} | Title: {chunk['title']} | Page: {chunk['page']} | "
        f"Section: {chunk['section_heading']}\n{chunk['text']}"
        for index, chunk in chunks_by_source.items()
    )
    audience_guidance = {
        "msme": "Explain practical preparation considerations for an MSME.",
        "manufacturer": "Explain practical preparation considerations for a manufacturer.",
        "consumer": "Use plain language for a consumer.",
        "student": "Briefly explain technical terms for a student.",
    }.get(user_type)
    prompt = (
        "Compare the user's product description with the supplied BIS chunks. Use ONLY the numbered chunks. "
        "List requirements an applicant must declare, prepare, test, or mark. Mark an item provided only if "
        "the description clearly covers it; missing if the document requires it and the description does not "
        "mention it; unclear if it is partly covered. Return at most 12 items. Every item needs a quote copied "
        "word for word from its numbered chunk, no more than 200 characters. Return ONLY JSON in this shape: "
        '{"product":"...","items":[{"requirement":"...","status":"provided|missing|unclear",'
        '"reason":"...","source":1,"quote":"exact words copied from chunk [source], max 200 characters"}]}. '
        f"Write requirement and reason in {language}; keep quotes in the original text. "
        f"{audience_guidance + ' ' if audience_guidance else ''}"
        f"User description: {description}\n\nNumbered chunks:\n{evidence}"
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
                raise ValueError("Could not parse Gemini's JSON response after two attempts.") from None

    verified_items = []
    for item in parsed["items"][:12]:
        source = item["source"]
        chunk = chunks_by_source.get(source)
        quote = item["quote"]
        verified = bool(chunk and len(quote) <= 200 and verify_quote(quote, chunk["text"])["verified"])
        if not verified:
            continue
        verified_items.append({
            "requirement": item["requirement"],
            "status": item["status"],
            "reason": item["reason"],
            "page": chunk["page"],
            "clause_ref": find_clause_ref(chunk["text"], quote),
            "quote": quote,
            "verified": True,
        })

    counts = {status: sum(item["status"] == status for item in verified_items)
              for status in ("provided", "missing", "unclear")}
    summary = (
        f"{counts['provided']} requirements provided, {counts['missing']} missing, "
        f"and {counts['unclear']} unclear."
    )
    return {
        "product": parsed.get("product") or metadata["title"],
        "is_number": metadata["is_number"],
        "items": verified_items,
        "counts": counts,
        "summary": summary,
    }
