import os
import time
import json
import asyncio
from typing import Optional

try:
    import openai
except Exception:
    openai = None

from app.db import SowKnowledgeStore
from app.vector_store import PineconeStore

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
INDEX_INTERVAL = int(os.getenv("EMBED_INDEX_INTERVAL", "3600"))  # seconds

if openai and OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

async def index_once(db_path: str = "data.sqlite"):
    """
    Index all SOWs/chats into embeddings and persist them to Pinecone (or fallback sqlite).
    """
    if not openai or not OPENAI_API_KEY:
        print("Embeddings indexer: OpenAI not configured, skipping.")
        return

    sow_store = SowKnowledgeStore(db_path=db_path)
    pine = PineconeStore(db_path=db_path)

    all_sows = []
    try:
        all_sows = sow_store.get_all()
    except Exception as e:
        print("indexer: failed to read sow_kb", str(e))
        return

    for s in all_sows:
        texts = []
        if s.get("filename"):
            texts.append(s["filename"])
        if s.get("features"):
            texts.append(" ".join(s["features"]))
        metadata = s.get("metadata") or {}
        if isinstance(metadata, dict):
            chat = metadata.get("chat") or []
            if chat:
                texts.append(" ".join([m.get("text","") for m in chat if isinstance(m.get("text",""), str)]))
            if metadata.get("description"):
                texts.append(str(metadata.get("description")))
        combined = "\n".join([t for t in texts if t])
        if not combined:
            continue

        try:
            resp = await asyncio.to_thread(openai.Embedding.create, model=OPENAI_EMBED_MODEL, input=combined)
            vector = resp["data"][0]["embedding"]
            pine.upsert_vector(s["id"], vector, metadata={"filename": s.get("filename")})
        except Exception as e:
            print(f"indexer: embedding failed for sow {s.get('id')}: {e}")

async def periodic_indexer(db_path: str = "data.sqlite", interval_seconds: int = INDEX_INTERVAL):
    if not openai or not OPENAI_API_KEY:
        print("Embeddings indexer disabled: OPENAI_API_KEY not set or openai package missing.")
        return

    while True:
        try:
            await index_once(db_path=db_path)
        except Exception as e:
            print("Embeddings indexer error:", e)
        await asyncio.sleep(interval_seconds)