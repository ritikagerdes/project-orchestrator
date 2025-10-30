from typing import Dict, List, Any, Optional
from datetime import datetime
import os
import re
import math
import json
import base64
import time
from collections import Counter

# try to import OpenAI SDK if available
try:
    import openai
except Exception:
    openai = None

from app.db import RateCardStore, SowKnowledgeStore

# Simple keyword list to detect features/integrations
FEATURE_KEYWORDS = [
    "auth", "login", "signup", "payment", "ecommerce", "shop", "cart", "checkout",
    "api", "integration", "crm", "hubspot", "reports", "dashboard", "analytics",
    "admin", "upload", "download", "image", "media", "wordpress", "blog", "search",
    "video", "stream", "newsletter", "billing", "account", "profile", "map", "zip"
]

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if openai and OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

class DevelopmentProposalOrchestrator:
    """
    Lightweight orchestrator implementing:
      - generate_clarifying_questions(text, client_info)
      - process_followup(text, answers, client_info)
      - process_client_input(text, client_info)
      - get_rate_card(), update_rate_card(card)
      - ingest_sow(parsed, metadata)
      - ingest_chat(messages, metadata)
    """

    def __init__(self, db_path: str = "data.sqlite"):
        self.db_path = db_path
        self.rate_store = RateCardStore(db_path=db_path)
        self.sow_store = SowKnowledgeStore(db_path=db_path)

    def _extract_features(self, text: str) -> List[str]:
        txt = (text or "").lower()
        found = []
        for k in FEATURE_KEYWORDS:
            if k in txt:
                found.append(k)
        # dedupe and return
        return sorted(set(found))

    def _historic_insights(self, features: List[str]) -> Dict[str, Any]:
        """
        Inspect stored SOWs/chat history to return:
          - similar_projects: list of metadata entries similar to current features
          - avg_final_price: average of recorded final_price values (or None)
          - common_questions: Counter of past bot questions seen in similar chats
        """
        all_rows = []
        try:
            all_rows = self.sow_store.get_all() or []
        except Exception:
            all_rows = []

        # compute avg final_price if available
        prices = [r.get("final_price", 0.0) for r in all_rows if r.get("final_price")]
        avg_final_price = sum(prices) / len(prices) if prices else None

        # find similar entries by feature overlap
        scores = []
        for r in all_rows:
            past_feats = r.get("features", [])
            overlap = len(set(features).intersection(set(past_feats)))
            scores.append((overlap, r))

        scores.sort(key=lambda x: x[0], reverse=True)
        similar = [r for s, r in scores if s > 0][:5]

        # collect past bot questions from similar chats stored in metadata.chat
        q_counter = Counter()
        for r in similar:
            meta = r.get("metadata", {}) or {}
            chat = meta.get("chat") or []
            for m in chat:
                # bot messages that look like questions
                if m.get("from") == "bot" and isinstance(m.get("text"), str) and m.get("text").strip().endswith("?"):
                    q_counter[m.get("text").strip()] += 1

        return {"similar_projects": similar, "avg_final_price": avg_final_price, "common_questions": q_counter}

    def generate_clarifying_questions(self, text: str, client_info: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Produce a short set (3-6) of generic clarifying questions.
        Leverage past SOWs/chats to surface common clarifications for similar projects.
        """
        features = self._extract_features(text)
        base_questions = [
            "What's the target launch timeframe (rough)?",
            "Who are the primary users of this product?",
            "Which core features must be included (e.g. auth, payments, search, user profiles)?"
        ]

        # add dynamic feature-specific prompts
        if any(k in ["payment", "ecommerce", "shop", "checkout", "cart"] for k in features):
            base_questions.append("Will payments be processed on the site? Which provider (Stripe, PayPal, other)?")
        if any(k in ["api", "integration", "crm", "hubspot"] for k in features):
            base_questions.append("Please list any third-party systems you must integrate with (CRM, payment, identity).")

        base_questions.append("Who will provide content (text/images)?")
        base_questions.append("Do you have a preferred budget range or ballpark figure?")

        # incorporate historically common questions for similar projects
        hist = self._historic_insights(features)
        common_qs = [q for q, cnt in hist["common_questions"].most_common(3)]
        # ensure uniqueness and keep ordering: prior common qs after base questions
        final = base_questions + [q for q in common_qs if q not in base_questions]
        return final[:6]

    def _call_openai_refine(self, text: str, answers: List[Dict[str, Any]], breakdown: Dict[str, Any], rate_card: Dict[str, float]) -> Optional[Dict[str, Any]]:
        """
        Call OpenAI with stricter parsing, schema validation, and retry logic.
        Expected JSON schema:
            { "adjusted_total_cost": number, "rationale": string (optional) }
        Retries up to 3 times with small backoff if parsing/validation fails.
        """
        if not openai or not OPENAI_API_KEY:
            return None

        schema = {
            "type": "object",
            "properties": {
                "adjusted_total_cost": {"type": "number"},
                "rationale": {"type": "string"}
            },
            "required": ["adjusted_total_cost"],
            "additionalProperties": False
        }

        system_msg = "You are an expert software services estimator. Return only a JSON object that matches the schema: { adjusted_total_cost: number, rationale?: string }"
        user_msg = (
            f"Project description:\n{text}\n\nClarifying answers:\n{json.dumps(answers, ensure_ascii=False)}\n\n"
            f"Role breakdown:\n{json.dumps(breakdown, ensure_ascii=False)}\n\nRate card:\n{json.dumps(rate_card, ensure_ascii=False)}\n\nReturn strictly the JSON object described."
        )

        attempts = 0
        max_attempts = 3
        backoff = 0.5
        while attempts < max_attempts:
            attempts += 1
            try:
                model = (os.getenv("OPENAI_MODEL") or "gpt-4")
                resp = openai.ChatCompletion.create(model=model, messages=[{"role":"system","content":system_msg},{"role":"user","content":user_msg}], temperature=0.0, max_tokens=300)
                text_out = resp.choices[0].message.get("content", "").strip()
                # Try to extract JSON object
                jstart = text_out.find("{")
                jend = text_out.rfind("}") + 1
                if jstart != -1 and jend != -1:
                    jtxt = text_out[jstart:jend]
                else:
                    jtxt = text_out

                parsed = json.loads(jtxt)
                # validate schema
                if jsonschema:
                    validate(instance=parsed, schema=schema)
                else:
                    # basic validation
                    if not isinstance(parsed, dict) or "adjusted_total_cost" not in parsed:
                        raise ValueError("Invalid response structure")
                    if not isinstance(parsed["adjusted_total_cost"], (int, float)):
                        raise ValueError("adjusted_total_cost must be a number")

                return parsed
            except Exception as e:
                # if last attempt, give up
                if attempts >= max_attempts:
                    print("OpenAI refine final failure:", str(e))
                    return None
                time.sleep(backoff * attempts)
                # retry
        return None

    def process_followup(self, text: str, answers: List[Dict[str, Any]], client_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Build an estimate from the original text + collected answers.
        If OPENAI_API_KEY is set, call OpenAI to refine final cost (scaffolded).
        """
        # revised heuristics
        base_hours = 40
        features = self._extract_features(text)
        feature_hours = len(features) * 12  # increased per-feature weight

        # clarity reduces uncertainty -> reduce contingency hours per answer
        clarity_reduction = len(answers) * 3

        # detect integration complexity
        extra_integrations = 0
        for a in answers:
            q = (a.get("question") or "").lower()
            ans = (a.get("answer") or "").lower()
            if "integrat" in q or "integrat" in ans:
                extra_integrations += max(0, len([s for s in re.split(r"[,\n;]+", ans) if s.strip()]) - 1)

        integration_hours = extra_integrations * 10

        total_hours_calc = base_hours + feature_hours + integration_hours - clarity_reduction
        total_hours = int(math.ceil(max(20, total_hours_calc)))  # enforce a sensible minimum

        # role distribution
        role_fracs = {
            "Software Developer": 0.50,
            "Senior Software Developer": 0.18,
            "Software Architect": 0.06,
            "WordPress Developer": 0.12,
            "Project Manager": 0.08,
            "Cloud Architect / DevOps Engineer": 0.06
        }

        rate_card = self.get_rate_card()
        for role in role_fracs.keys():
            if role not in rate_card:
                rate_card[role] = 90.0

        # calculate cost per role
        breakdown = {}
        raw_total_cost = 0.0
        for role, frac in role_fracs.items():
            hrs = int(round(total_hours * frac))
            rate = float(rate_card.get(role, 90.0))
            cost = round(hrs * rate, 2)
            breakdown[role] = {"hours": hrs, "rate": rate, "cost": cost}
            raw_total_cost += cost

        # Use ML model (OpenAI) to refine final cost if available
        adjusted_total_cost = raw_total_cost
        ml_note = None
        ml_resp = self._call_openai_refine(text, answers, breakdown, rate_card)
        if isinstance(ml_resp, dict) and ml_resp.get("adjusted_total_cost"):
            try:
                adjusted_total_cost = float(ml_resp["adjusted_total_cost"])
                ml_note = ml_resp.get("rationale") or ml_resp.get("note")
            except Exception:
                adjusted_total_cost = raw_total_cost

        # fallback historical smoothing if no ML
        if ml_resp is None:
            hist = self._historic_insights(features)
            avg_hist_price = hist.get("avg_final_price")
            if avg_hist_price:
                adjusted_total_cost = round(raw_total_cost * 0.6 + avg_hist_price * 0.4, 2)

        # Build SOW text
        sow_lines = [
            f"SOW Summary - generated {datetime.utcnow().isoformat()}Z",
            "",
            "Client description:",
            text,
            "",
            "Clarifying answers provided:"
        ]
        for a in answers:
            q = a.get("question") or a.get("q") or ""
            ans = a.get("answer") or a.get("a") or ""
            sow_lines.append(f"- {q}: {ans}")
        sow_lines += ["", "Estimate breakdown:"]
        for role, info in breakdown.items():
            sow_lines.append(f"- {role}: {info['hours']} hrs @ ${info['rate']}/hr = ${info['cost']}")
        sow_lines += ["", f"Raw estimate total: ${round(raw_total_cost,2)}", f"Adjusted total: ${round(adjusted_total_cost,2)}"]
        if ml_note:
            sow_lines += ["", "Estimator note (ML):", ml_note]

        sow_text = "\n".join(sow_lines)
        sow_b64 = base64.b64encode(sow_text.encode("utf-8")).decode("utf-8")

        # persist SOW to knowledge base (include computed adjusted cost)
        try:
            parsed = {"features": features, "final_price": adjusted_total_cost}
            self.ingest_sow(parsed, {"name": f"generated-{int(datetime.utcnow().timestamp())}.txt"})
        except Exception:
            pass

        return {
            "status": "completed",
            "summary": f"Estimated {total_hours} hours, ${round(adjusted_total_cost,2)} total.",
            "estimate": {"totalHours": total_hours, "totalCost": round(adjusted_total_cost, 2), "breakdown": breakdown},
            "sow": sow_b64
        }

    def process_client_input(self, text: str, client_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Entry point used by /api/message when no answers provided.
        Return clarifying questions or immediate estimate if description is very specific.
        """
        if isinstance(text, str) and (len(text) > 400 or re.search(r"\$(\d+)", text) or "budget" in text.lower()):
            return self.process_followup(text, [], client_info or {})
        qs = self.generate_clarifying_questions(text, client_info)
        return {"requires_clarification": True, "questions": qs}

    def get_rate_card(self) -> Dict[str, float]:
        try:
            return self.rate_store.get_rate_card() or {}
        except Exception:
            return {
                "Software Developer": 80.0,
                "Senior Software Developer": 120.0,
                "Software Architect": 150.0,
                "WordPress Developer": 70.0,
                "Project Manager": 95.0,
                "Cloud Architect / DevOps Engineer": 140.0
            }

    def update_rate_card(self, new_card: Dict[str, float]):
        try:
            canonical = {
                "Software Developer",
                "Senior Software Developer",
                "Software Architect",
                "WordPress Developer",
                "Project Manager",
                "Cloud Architect / DevOps Engineer"
            }
            filtered = {r: float(new_card[r]) for r in new_card if r in canonical}
            if filtered:
                self.rate_store.update_rate_card(filtered)
        except Exception:
            pass

    def ingest_sow(self, parsed: Dict[str, Any], metadata: Dict[str, Any]):
        try:
            self.sow_store.insert(parsed, metadata)
        except Exception:
            pass

    def ingest_chat(self, messages: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None):
        """
        Persist chat transcript as an entry in the SOW KB so it can be used as training.
        Attempts to extract final_price if present in bot messages (simple dollar regex).
        """
        try:
            meta = metadata or {}
            meta["chat"] = messages
            # features from combined bot+user text
            combined = " ".join([m.get("text", "") for m in messages if isinstance(m.get("text", ""), str)])
            feats = self._extract_features(combined)
            # try to extract a dollar amount from bot messages as final price
            final_price = None
            for m in messages[::-1]:
                if m.get("from") == "bot" and isinstance(m.get("text"), str):
                    mm = re.search(r"\$?([0-9]{3,}(?:\.[0-9]{1,2})?)", m["text"].replace(",", ""))
                    if mm:
                        try:
                            final_price = float(mm.group(1))
                            break
                        except Exception:
                            pass
            parsed = {"features": feats, "final_price": final_price or 0.0}
            # name for metadata if not provided
            metadata_name = meta.get("name") or f"chat-{int(datetime.utcnow().timestamp())}.txt"
            self.ingest_sow(parsed, {"name": metadata_name, **meta})
        except Exception:
            pass