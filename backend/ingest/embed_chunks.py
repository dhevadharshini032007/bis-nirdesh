import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
CHUNKS_PATH = PROJECT_ROOT / "data" / "chunks.json"
EMBEDDINGS_PATH = PROJECT_ROOT / "data" / "embeddings.json"
BATCH_SIZE = 20
MAX_ATTEMPTS = 5
BATCH_PAUSE_SECONDS = 15


def main():
    load_dotenv(ENV_PATH, override=True)
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_EMBEDDING_MODEL")
    if not api_key:
        raise ValueError(f"GEMINI_API_KEY is missing or empty; checked {ENV_PATH}")
    if not model:
        raise ValueError("GEMINI_EMBEDDING_MODEL is missing or empty in backend/.env")

    chunks = json.loads(CHUNKS_PATH.read_text(encoding="utf-8-sig"))
    existing_results = (
        json.loads(EMBEDDINGS_PATH.read_text(encoding="utf-8-sig"))
        if EMBEDDINGS_PATH.exists()
        else []
    )
    embeddings_by_id = {item["chunk_id"]: item for item in existing_results}
    missing_chunks = [chunk for chunk in chunks if chunk["chunk_id"] not in embeddings_by_id]
    client = genai.Client(api_key=api_key)
    results = list(existing_results)
    failed_chunk_ids = []

    try:
        for batch_start in range(0, len(missing_chunks), BATCH_SIZE):
            batch = missing_chunks[batch_start:batch_start + BATCH_SIZE]
            embedded_batch = None
            last_error = None
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    response = client.models.embed_content(
                        model=model,
                        contents=[chunk["embed_text"] for chunk in batch],
                    )
                    vectors = response.embeddings or []
                    if len(vectors) != len(batch):
                        raise ValueError("Embedding response count did not match batch size")
                    embedded_batch = [
                        {"chunk_id": chunk["chunk_id"], "embedding": vector.values}
                        for chunk, vector in zip(batch, vectors)
                    ]
                    break
                except Exception as error:
                    last_error = error
                    if attempt < MAX_ATTEMPTS:
                        error_message = str(error)
                        is_quota_error = any(
                            marker in error_message.lower()
                            for marker in ("429", "quota", "resource_exhausted")
                        )
                        time.sleep(60 if is_quota_error else 2)

            if embedded_batch is None:
                failed_chunk_ids.extend(chunk["chunk_id"] for chunk in batch)
                safe_error_message = str(last_error).replace(api_key, "[REDACTED]")
                print(f"Batch failed after {MAX_ATTEMPTS} attempts: {safe_error_message}")
                print("Failed chunks: " + ", ".join(chunk["chunk_id"] for chunk in batch))
            else:
                results.extend(embedded_batch)
                embeddings_by_id.update({item["chunk_id"]: item for item in embedded_batch})

            if batch_start + BATCH_SIZE < len(missing_chunks):
                time.sleep(BATCH_PAUSE_SECONDS)
    finally:
        results = [embeddings_by_id[chunk["chunk_id"]] for chunk in chunks if chunk["chunk_id"] in embeddings_by_id]
        EMBEDDINGS_PATH.write_text(
            json.dumps(results, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"Chunks embedded: {len(results)} out of {len(chunks)}")
    if results:
        print(f"Embedding length: {len(results[0]['embedding'])}")
    else:
        print("Embedding length: unavailable (no chunks embedded)")


if __name__ == "__main__":
    main()


