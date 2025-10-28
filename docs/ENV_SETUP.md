# Environment / Setup Notes

Required environment variables (backend):
- OPENAI_API_KEY            -> required for ML refine + embeddings
- OPENAI_MODEL             -> optional (e.g. "gpt-4" or "gpt-3.5-turbo")
- OPENAI_EMBED_MODEL       -> optional (default "text-embedding-3-small")
- PINECONE_API_KEY         -> optional (enable Pinecone vector DB)
- PINECONE_ENV             -> optional (Pinecone environment/region)
- PINECONE_INDEX           -> optional (default "project-orchestrator-index")
- DB_PATH                  -> optional (path to sqlite DB, default "data.sqlite")
- DROPBOX_TOKEN            -> optional (if using Dropbox ingestion)

Python dependencies (backend)
One-liner (run inside backend venv):
python -m pip install --upgrade pip && python -m pip install reportlab openai pinecone-client jsonschema

Notes:
- If you want Pinecone enabled, set PINECONE_API_KEY and PINECONE_ENV before starting the backend.
- For embeddings indexing and refine, set OPENAI_API_KEY.
- After changing env vars restart the backend (uvicorn) so the startup task picks them up.