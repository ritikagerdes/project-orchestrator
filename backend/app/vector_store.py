"""
Pinecone-backed vector store abstraction with a SQLite fallback.
Uses environment variables:
  - PINECONE_API_KEY
  - PINECONE_ENV (region)
  - PINECONE_INDEX (index name)
If Pinecone not configured, writes vectors to the existing EmbeddingStore in db.py
"""
import os
import json
try:
    import pinecone
except Exception:
    pinecone = None

from typing import List, Dict, Any, Optional
from app.db import EmbeddingStore, get_engine

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENV")  # e.g. "us-west1-gcp"
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "project-orchestrator-index")


class PineconeStore:
    def __init__(self, db_path: str = "data.sqlite"):
        self.db_path = db_path
        self.fallback = EmbeddingStore(db_path=db_path)
        self.enabled = False

        if pinecone and PINECONE_API_KEY and PINECONE_ENV:
            try:
                pinecone.init(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)
                # create index if doesn't exist
                existing = pinecone.list_indexes()
                if PINECONE_INDEX not in existing:
                    # dimension unknown here; the upsert path will create vectors with dimension from embeddings
                    # create a small default index (you may change metric next)
                    pinecone.create_index(PINECONE_INDEX, dimension=1536, metric="cosine")
                self.index = pinecone.Index(PINECONE_INDEX)
                self.enabled = True
            except Exception:
                self.enabled = False
        else:
            self.enabled = False

    def upsert_vector(self, sow_id: int, vector: List[float], metadata: Optional[Dict[str, Any]] = None):
        if self.enabled:
            try:
                # Pinecone requires string ids
                self.index.upsert([(str(sow_id), vector, metadata or {})])
                return True
            except Exception:
                # fallback to sqlite store
                self.fallback.upsert_embedding(sow_id, vector, metadata or {})
                return False
        else:
            self.fallback.upsert_embedding(sow_id, vector, metadata or {})
            return False

    def fetch_vector(self, sow_id: int) -> Optional[List[float]]:
        if self.enabled:
            try:
                resp = self.index.fetch(ids=[str(sow_id)])
                vectors = resp.get("vectors") or {}
                vobj = vectors.get(str(sow_id))
                if not vobj:
                    return None
                return vobj.get("values")
            except Exception:
                return None
        else:
            rows = self.fallback.get_all()
            for r in rows:
                if r.get("sow_id") == sow_id:
                    return r.get("vector")
            return None

    def query(self, vector: List[float], top_k: int = 5):
        if self.enabled:
            resp = self.index.query(vector=vector, top_k=top_k, include_metadata=True)
            return resp.get("matches", [])
        else:
            # basic brute force similarity on fallback (not optimized)
            rows = self.fallback.get_all()
            import math
            def cosine(a,b):
                dot = sum(x*y for x,y in zip(a,b))
                mag = math.sqrt(sum(x*x for x in a))*math.sqrt(sum(y*y for y in b))
                return dot/(mag+1e-9)
            out = []
            for r in rows:
                v = r.get("vector") or []
                if not v: continue
                score = cosine(vector, v)
                out.append({"id": r.get("sow_id"), "score": score, "metadata": r.get("metadata")})
            out.sort(key=lambda x: x["score"], reverse=True)
            return out[:top_k]