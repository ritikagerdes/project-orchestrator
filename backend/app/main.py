from fastapi import FastAPI, HTTPException, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import os
import json
import base64

from app.db import get_db, init_db, DEFAULT_RATE_CARD
from app.agents import DevelopmentProposalOrchestrator
from app.dropbox_client import DropboxClient
from app.sow_parsing import SowParser
from app.models import RateCardIn, RateCardOut

app = FastAPI(title="Proposal Orchestrator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Init DB + orchestrator
DB_PATH = os.getenv("DB_PATH", "data.sqlite")
init_db(DB_PATH)
orchestrator = DevelopmentProposalOrchestrator(db_path=DB_PATH)

# Dropbox + SOW parser (optional)
DROPBOX_TOKEN = os.getenv("DROPBOX_TOKEN", "")
dropbox_client = DropboxClient(DROPBOX_TOKEN) if DROPBOX_TOKEN else None
sow_parser = SowParser()

# Models
class ClientInput(BaseModel):
    text: str
    client_info: Optional[Dict[str, Any]] = {}
    # optional mode: "production" | "stage"
    mode: Optional[str] = "production"

class ImportSowsRequest(BaseModel):
    dropbox_path: str = "/SOWs"

class AdminSettings(BaseModel):
    chat_enabled: bool = True
    chat_position: str = "bottom-right"  # bottom-right | bottom-left

SETTINGS_FILE = os.path.join(os.getcwd(), "backend_admin_settings.json")

def _read_settings() -> Dict[str, Any]:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return AdminSettings().dict()

def _write_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
    s = AdminSettings(**payload).dict()
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
    return s

@app.get("/", include_in_schema=False)
async def root():
    # return a simple JSON-serializable dict (FastAPI handles serialization)
    return {"message": "Proposal Orchestrator backend running. Open /docs for API docs."}

@app.post("/api/message")
def process_message(payload: ClientInput):
    """
    Accepts:
      { text: str, client_info?: {...}, mode?: "production" | "stage" }
    Behavior:
      - If client_info.answers is present (array of {question, answer}), treat as follow-up:
          * Try to let the orchestrator handle it (orchestrator.process_followup)
          * Fallback: produce a simple heuristic estimate and base64-encoded SOW
      - If no answers: return a list of clarifying questions (from orchestrator if available,
        otherwise a sensible default) so frontend can ask them one-by-one.
    """
    text = (payload.text or "").strip()
    client_info = payload.client_info or {}
    client_info["_env"] = payload.mode or "production"

    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    answers = client_info.get("answers")  # expected: [{question: "...", answer: "..."}, ...]

    try:
        # follow-up with collected answers
        if answers:
            if hasattr(orchestrator, "process_followup"):
                return orchestrator.process_followup(text, answers, client_info)
            # fallback simple estimator (should rarely run because orchestrator implements followup)
            base_hours = 40
            features = []
            # try extracting features if parser exists
            try:
                features = sow_parser.parse(text).get("features", [])
            except Exception:
                features = []
            feature_hours = len(features) * 12
            integration_hours = 0
            for a in answers:
                q = (a.get("question") or "").lower()
                ans = (a.get("answer") or "").lower()
                if "integrat" in q or "integrat" in ans:
                    integration_hours += max(0, len([s for s in re.split(r"[,\n;]+", ans) if s.strip()]) - 1) * 10
            clarity_reduction = len(answers) * 3
            total_hours = int(max(20, base_hours + feature_hours + integration_hours - clarity_reduction))
            avg_rate = 90.0
            total_cost = round(total_hours * avg_rate, 2)
            sow_text = f"Estimate (fallback): {total_hours} hours, ${total_cost}\n\nAnswers:\n" + "\n".join([f"- {a.get('question')}: {a.get('answer')}" for a in answers])
            sow_b64 = base64.b64encode(sow_text.encode("utf-8")).decode("utf-8")
            return {"status": "completed", "summary": "Fallback estimate", "estimate": {"totalHours": total_hours, "totalCost": total_cost}, "sow": sow_b64}

        # initial message -> ask clarifying questions via orchestrator or default
        if hasattr(orchestrator, "process_client_input"):
            return orchestrator.process_client_input(text, client_info)
        # default questions (should be handled by orchestrator)
        QUESTIONS = [
            "What's the target launch timeframe (rough)?",
            "Who are the primary users of this product?",
            "Which core features must be included (e.g. auth, payments, search, user profiles)?",
            "Any required third-party integrations (CRM, payment, identity)?",
            "Who will provide content (text/images)?",
            "Do you have a preferred budget range or ballpark figure?"
        ]
        return {"requires_clarification": True, "questions": QUESTIONS}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Admin ratecard endpoints (tolerant of payload shape)
@app.get("/api/admin/ratecard", response_model=RateCardOut)
async def get_rate_card(db = Depends(get_db)):
    try:
        store = db or None
        if store is None:
            if hasattr(orchestrator, "get_rate_card"):
                card = orchestrator.get_rate_card() or DEFAULT_RATE_CARD.copy()
            else:
                card = DEFAULT_RATE_CARD.copy()
        else:
            card = store.get_rate_card() or DEFAULT_RATE_CARD.copy()
    except Exception:
        card = DEFAULT_RATE_CARD.copy()
    return {"rates": card}

@app.put("/api/admin/ratecard")
def update_rate_card(payload: Dict[str, Any] = Body(...), db = Depends(get_db)):
    if isinstance(payload, dict) and "rates" in payload and isinstance(payload["rates"], dict):
        card = payload["rates"]
    else:
        card = payload

    try:
        if hasattr(orchestrator, "update_rate_card"):
            orchestrator.update_rate_card(card)
        else:
            raise RuntimeError("orchestrator cannot update rate card")
    except Exception:
        try:
            store = db or None
            if store is not None:
                store.update_rate_card(card)
        except Exception:
            pass

    return {"status": "ok"}

@app.post("/api/admin/import_sows")
def import_sows(req: ImportSowsRequest):
    if not dropbox_client:
        raise HTTPException(status_code=400, detail="DROPBOX_TOKEN not configured")

    try:
        files = dropbox_client.list_files(req.dropbox_path)
        imported = 0
        for f in files:
            content = dropbox_client.download_file(f["path_lower"])
            parsed = sow_parser.parse(content)
            orchestrator.ingest_sow(parsed, f)
            imported += 1
        return {"imported": imported}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Admin settings endpoints
@app.get("/api/admin/settings")
def get_admin_settings():
    return _read_settings()

@app.put("/api/admin/settings")
def put_admin_settings(payload: AdminSettings):
    data = _write_settings(payload.dict())
    return data