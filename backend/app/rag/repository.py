"""Small cited evidence corpus backed by Qdrant with deterministic embeddings."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from app.core.logging import get_logger
from app.db import get_datastores

log = get_logger("rag.repository")
COLLECTION = "chanakya_evidence"
DIMENSIONS = 96
_CORPUS_PATH = Path(__file__).with_name("corpus.json")


def _documents() -> list[dict]:
    return json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))


def _embed(text: str) -> list[float]:
    vector = [0.0] * DIMENSIONS
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        index = int.from_bytes(digest[:2], "big") % DIMENSIONS
        vector[index] += -1.0 if digest[2] & 1 else 1.0
    norm = sum(v * v for v in vector) ** 0.5 or 1.0
    return [v / norm for v in vector]


class EvidenceStore:
    async def ensure_corpus(self) -> int:
        client = get_datastores().qdrant
        docs = _documents()
        if client is None:
            return 0
        try:
            from qdrant_client.models import Distance, PointStruct, VectorParams
            existing = {c.name for c in client.get_collections().collections}
            if COLLECTION not in existing:
                client.create_collection(
                    collection_name=COLLECTION,
                    vectors_config=VectorParams(size=DIMENSIONS, distance=Distance.COSINE),
                )
            points = [PointStruct(
                id=int(hashlib.sha256(doc["id"].encode()).hexdigest()[:15], 16),
                vector=_embed(f"{doc['title']} {doc['section']} {doc['text']}"),
                payload={**doc, "content_hash": hashlib.sha256(doc["text"].encode()).hexdigest()},
            ) for doc in docs]
            client.upsert(collection_name=COLLECTION, points=points, wait=True)
            return len(points)
        except Exception as exc:  # noqa: BLE001
            log.warning("rag.seed_failed", error=str(exc))
            return 0

    async def search(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        client = get_datastores().qdrant
        if client is not None:
            try:
                hits = client.search(collection_name=COLLECTION, query_vector=_embed(query),
                                     limit=limit, with_payload=True)
                return [{**dict(hit.payload or {}), "score": round(float(hit.score), 3)}
                        for hit in hits]
            except Exception as exc:  # noqa: BLE001
                log.debug("rag.search_degraded", error=str(exc))
        tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
        ranked = []
        for doc in _documents():
            haystack = set(re.findall(r"[a-z0-9]+", f"{doc['title']} {doc['text']}".lower()))
            ranked.append((len(tokens & haystack), doc))
        return [{**doc, "score": score} for score, doc in sorted(ranked, reverse=True,
                                                                 key=lambda item: item[0])[:limit]]


evidence_store = EvidenceStore()
