"""
Shared embedding helpers for the RAG lessons.

embed(texts, task_type)  one 768-number vector per text, from Gemini
cosine(a, b)             similarity of two vectors (see lesson 1)

Embeddings cost an API call, and the same text always gives the same
vector, so every result is cached on disk in rag/.cache/ (gitignored),
keyed by a hash of the model, size, task type and text. Re-running a
lesson only pays for text that changed.

The free Gemini tier allows 100 embeddings a minute (each text counts),
so big jobs are sent in batches of 45 with a pause between them, and a
"429 slow down" reply is waited out and retried.
"""

import hashlib
import json
import math
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

load_dotenv(".env")

MODEL = "gemini-embedding-2"
DIMENSIONS = 768
BATCH = 45          # texts per API call
PAUSE_SECONDS = 30  # between batches: 45 texts per 30 s stays under 100 a minute

CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "embeddings.json")
_client = None
_cache = None


def _load_cache():
    global _cache
    if _cache is None:
        try:
            with open(CACHE_PATH, encoding="utf-8") as f:
                _cache = json.load(f)
        except FileNotFoundError:
            _cache = {}
    return _cache


def _save_cache():
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(_cache, f)


def _key(text, task_type):
    return hashlib.sha256(f"{MODEL}|{DIMENSIONS}|{task_type}|{text}".encode("utf-8")).hexdigest()


def embed(texts, task_type):
    """task_type is RETRIEVAL_DOCUMENT for passages, RETRIEVAL_QUERY for questions."""
    global _client
    cache = _load_cache()
    missing = [t for t in dict.fromkeys(texts) if _key(t, task_type) not in cache]
    if missing:
        if _client is None:
            _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        for start in range(0, len(missing), BATCH):
            if start:
                print(f"  embedded {start}/{len(missing)}, pausing {PAUSE_SECONDS}s for the rate limit...")
                time.sleep(PAUSE_SECONDS)
            batch = missing[start:start + BATCH]
            for e, text in zip(_embed_batch(batch, task_type), batch):
                cache[_key(text, task_type)] = e.values
            _save_cache()  # keep progress if a later batch fails
    return [cache[_key(t, task_type)] for t in texts]


def _embed_batch(batch, task_type, tries=5):
    for attempt in range(tries):
        try:
            # One Content per text; a plain list of strings would be merged into one vector.
            return _client.models.embed_content(
                model=MODEL,
                contents=[types.Content(parts=[types.Part(text=t)]) for t in batch],
                config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=DIMENSIONS),
            ).embeddings
        except errors.ClientError as e:
            if e.code != 429 or attempt == tries - 1:
                raise
            print("  rate limit hit, waiting 30s and retrying...")
            time.sleep(30)


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))
