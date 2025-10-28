from fastapi import FastAPI, HTTPException, Depends, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import os
import time
import base64
import io
from uuid import uuid4
from pathlib import Path
from fastapi import Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from app.hubspot_client import create_contact, create_note_for_contact
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import zipfile
import tempfile

from app.db import get_db, init_db, DEFAULT_RATE_CARD
from app.agents import DevelopmentProposalOrchestrator
from app.dropbox_client import DropboxClient
from app.sow_parsing import SowParser
from app.models import RateCardIn, RateCardOut
import asyncio
from app.embeddings_indexer import index_once, periodic_indexer
from app.vector_store import PineconeStore

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
        # Always update the persistent store first (so DB reflects changes)
        try:
            store = db or None
            if store is not None:
                store.update_rate_card(card)
        except Exception:
            # swallow — will try orchestrator below
            pass

        # Then notify orchestrator so its cache/logic is in sync (if implemented)
        try:
            if hasattr(orchestrator, "update_rate_card"):
                orchestrator.update_rate_card(card)
        except Exception:
            pass

        # Return the authoritative current rate card (read from DB if available)
        try:
            store = db or None
            if store is not None:
                current = store.get_rate_card()
            elif hasattr(orchestrator, "get_rate_card"):
                current = orchestrator.get_rate_card()
            else:
                current = DEFAULT_RATE_CARD.copy()
        except Exception:
            current = DEFAULT_RATE_CARD.copy()

        return {"status": "ok", "rates": current}
    except Exception:
        return {"status": "error"}

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

@app.post("/api/chat/save")
def save_chat(payload: Dict[str, Any] = Body(...)):
    """
    Save chat/messages into SowKnowledgeStore (metadata includes chat).
    payload: { title?: str, messages: [ {from, text} ], meta?: {} }
    Persist via orchestrator.ingest_chat so historic chats are usable for training/insights.
    """
    msgs = payload.get("messages") or []
    title = payload.get("title") or f"chat-{int(datetime.utcnow().timestamp())}.txt"
    meta = payload.get("meta") or {}
    try:
        # use orchestrator ingest_chat to persist and extract features/prices
        orchestrator.ingest_chat(msgs, {"name": title, **meta})
        return {"status": "ok", "saved_as": title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _make_pdf_bytes(sow_text: str, estimate: dict, title: str = "Project Quote") -> bytes:
    """
    Simple PDF renderer using reportlab. Produces a readable multi-page PDF.
    """
    try:
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        width, height = letter

        margin_x = 72
        y = height - 72

        # Title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(margin_x, y, title)
        y -= 28

        # metadata / estimate summary (if present)
        if estimate:
            c.setFont("Helvetica-Bold", 12)
            c.drawString(margin_x, y, "Estimate Summary")
            y -= 18
            c.setFont("Helvetica", 10)
            summary_lines = []
            if estimate.get("totalCost") is not None:
                summary_lines.append(f"Total cost: ${estimate.get('totalCost')}")
            if estimate.get("totalHours") is not None:
                summary_lines.append(f"Total hours: {estimate.get('totalHours')}")
            for ln in summary_lines:
                if y < 72:
                    c.showPage()
                    y = height - 72
                    c.setFont("Helvetica", 10)
                c.drawString(margin_x, y, ln)
                y -= 14
            y -= 6

        # SOW / body
        c.setFont("Helvetica-Bold", 12)
        if y < 72:
            c.showPage()
            y = height - 72
        c.drawString(margin_x, y, "SOW / Details")
        y -= 18
        c.setFont("Helvetica", 10)

        for raw_line in (sow_text or "").splitlines():
            line = raw_line.rstrip()
            # wrap long lines to page width
            while line:
                # approx characters per line
                max_chars = 95
                piece = line[:max_chars]
                line = line[max_chars:]
                if y < 72:
                    c.showPage()
                    y = height - 72
                    c.setFont("Helvetica", 10)
                c.drawString(margin_x, y, piece)
                y -= 14

        c.save()
        buf.seek(0)
        return buf.read()
    except Exception as e:
        # bubble up to caller
        raise

@app.post("/api/sow/pdf")
def generate_sow_pdf(payload: Dict[str, Any] = Body(...)):
    """
    payload: { sow_text?: str, sow_b64?: base64str, estimate?: {...}, title?: str }
    Returns binary PDF stream.
    """
    sow_text = payload.get("sow_text") or ""
    sow_b64 = payload.get("sow_b64")
    if sow_b64:
        try:
            sow_text = base64.b64decode(sow_b64).decode("utf-8")
        except Exception:
            # ignore decode error and fallback to provided sow_text
            pass
    estimate = payload.get("estimate") or {}
    title = payload.get("title") or "Project Quote"

    try:
        pdf_bytes = _make_pdf_bytes(sow_text, estimate, title)
        return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers={
            "Content-Disposition": f'attachment; filename="{title.replace(" ", "_")}.pdf"'
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hubspot/send")
def send_to_hubspot(payload: Dict[str, Any] = Body(...)):
    """
    payload: { name, email, message, sow_b64?, chat?: messages[] }
    Creates a contact and a note with SOW/chat.
    """
    name = payload.get("name")
    email = payload.get("email")
    message = payload.get("message", "")
    sow_b64 = payload.get("sow_b64")
    chat = payload.get("chat", [])

    if not email or not name:
        raise HTTPException(status_code=400, detail="name and email required")

    try:
        contact = create_contact(name=name, email=email, extra={"notes": message})
        contact_id = contact.get("id")
        note_text = f"Project quote from chat. Message: {message}\n\nChat transcript:\n"
        for m in (chat or []):
            who = m.get("from")
            text = m.get("text")
            note_text += f"{who}: {text}\n"
        if sow_b64:
            try:
                sow_text = base64.b64decode(sow_b64).decode("utf-8")
                note_text += "\nSOW:\n" + sow_text
            except Exception:
                pass
        # create a note and associate
        create_note_for_contact(contact_id, note_text)
        return {"status": "ok", "contact_id": contact_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup_tasks():
    # start embeddings indexer in background if configured
    db_path = DB_PATH
    try:
        # run periodic_indexer as a background task only if OPENAI_API_KEY present
        if os.getenv("OPENAI_API_KEY"):
            # schedule background coroutine
            asyncio.create_task(periodic_indexer(db_path=db_path))
            print("Started embeddings periodic indexer (background task).")
        else:
            print("OPENAI_API_KEY not set; embeddings indexer not started.")
    except Exception as e:
        print("startup_tasks error:", e)

# ensure DB_PATH defined
DB_PATH = os.getenv("DB_PATH", "data.sqlite")

# create folder to store generated PDFs
SOW_DIR = Path(__file__).resolve().parents[1] / "sow_files"
SOW_DIR.mkdir(parents=True, exist_ok=True)

# mount static files so generated PDFs are downloadable
app.mount("/sow", StaticFiles(directory=str(SOW_DIR)), name="sow_files")

@app.post("/api/sow/create")
def create_sow_pdf(payload: Dict[str, Any] = Body(...), request: Request = None):
    """
    Persist a generated SOW/estimate PDF on disk and return a download URL.
    payload: { sow_text?: str, sow_b64?: base64str, estimate?: {...}, title?: str }
    """
    sow_text = payload.get("sow_text", "")
    sow_b64 = payload.get("sow_b64")
    if sow_b64:
        try:
            sow_text = base64.b64decode(sow_b64).decode("utf-8")
        except Exception:
            # if not decodable, treat sow_b64 as raw text
            sow_text = sow_b64

    estimate = payload.get("estimate") or {}
    title = payload.get("title") or "Project_Quote"

    try:
        pdf_bytes = _make_pdf_bytes(sow_text, estimate, title)
        filename = f"{int(time.time())}-{uuid4().hex}.pdf"
        out_path = SOW_DIR / filename
        with open(out_path, "wb") as fh:
            fh.write(pdf_bytes)

        base = ""
        if request:
            base = str(request.base_url).rstrip("/")
        download_url = f"{base}/sow/{filename}" if base else f"/sow/{filename}"
        return {"status": "ok", "download_url": download_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/share/zip")
def create_share_zip(payload: Dict[str, Any] = Body(...), request: Request = None):
    """
    Create a ZIP containing:
      - chat text file (chat-<timestamp>.txt)
      - quote PDF (if sow_b64 present) (quote-<timestamp>.pdf)
    Returns the ZIP as a FileResponse for immediate download.
    payload: { messages: [{from, text}], sow_b64?: base64str, estimate?: {...}, title?: str }
    """
    try:
        title = payload.get("title") or f"share-{int(time.time())}"
        messages = payload.get("messages", [])
        sow_b64 = payload.get("sow_b64")
        estimate = payload.get("estimate") or {}

        # ensure output directory exists
        out_dir = SOW_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        # write chat text
        chat_filename = f"{title}-chat.txt"
        chat_path = out_dir / chat_filename
        with open(chat_path, "w", encoding="utf-8") as fh:
            for m in messages:
                who = m.get("from", "unknown")
                text = (m.get("text") or "").replace("\r", "")
                fh.write(f"{who}: {text}\n\n")

        files_to_zip = [chat_path]

        # create PDF if sow_b64 provided
        if sow_b64:
            try:
                sow_text = base64.b64decode(sow_b64).decode("utf-8")
            except Exception:
                sow_text = sow_b64 or ""
            pdf_bytes = _make_pdf_bytes(sow_text, estimate, title)
            pdf_filename = f"{title}-quote.pdf"
            pdf_path = out_dir / pdf_filename
            with open(pdf_path, "wb") as fh:
                fh.write(pdf_bytes)
            files_to_zip.append(pdf_path)

        # create zip
        zip_filename = f"{title}.zip"
        zip_path = out_dir / zip_filename
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in files_to_zip:
                zf.write(p, arcname=p.name)

        # return zip as file response
        return FileResponse(path=str(zip_path), media_type="application/zip", filename=zip_filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/embeddings")
def admin_list_embeddings(db = Depends(get_db)):
    """
    Return list of SOWs and whether they have embeddings in the vector store.
    """
    try:
        sow_store = db.__class__(db_path=DB_PATH) if db else None
    except Exception:
        sow_store = None

    pine = PineconeStore(db_path=DB_PATH)
    rows = []
    try:
        sow_kb = SowKnowledgeStore(db_path=DB_PATH)
        all_sows = sow_kb.get_all()
        for s in all_sows:
            has_vector = False
            try:
                v = pine.fetch_vector(s["id"])
                has_vector = bool(v)
            except Exception:
                has_vector = False
            rows.append({"id": s["id"], "filename": s.get("filename"), "final_price": s.get("final_price"), "has_vector": has_vector, "metadata": s.get("metadata")})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "ok", "items": rows}

@app.post("/api/admin/reindex")
async def admin_reindex(background: bool = Body(True)):
    """
    Trigger a reindex. If background True, schedule and return immediately.
    """
    try:
        if background:
            # schedule background task
            import asyncio
            asyncio.create_task(index_once(db_path=DB_PATH))
            return {"status": "ok", "message": "Reindex scheduled"}
        else:
            await index_once(db_path=DB_PATH)
            return {"status": "ok", "message": "Reindex completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))