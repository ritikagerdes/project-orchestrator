from typing import Dict, List, Any, Optional
from datetime import datetime
import re
import math
import json
import base64
from app.db import RateCardStore, SowKnowledgeStore

# Simple keyword list to detect features/integrations
FEATURE_KEYWORDS = [
    "auth", "login", "signup", "payment", "ecommerce", "shop", "cart", "checkout",
    "api", "integration", "crm", "hubspot", "reports", "dashboard", "analytics",
    "admin", "upload", "download", "image", "media", "wordpress", "blog"
]

class DevelopmentProposalOrchestrator:
    """
    Lightweight orchestrator implementing:
      - generate_clarifying_questions(text, client_info)
      - process_followup(text, answers, client_info)
      - process_client_input(text, client_info)  (basic entrypoint if needed)
      - get_rate_card(), update_rate_card(card)
      - ingest_sow(parsed, metadata)
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

    def generate_clarifying_questions(self, text: str, client_info: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Produce a short set (3-6) of generic clarifying questions.
        Keep it lightweight — not a full SOW.
        """
        features = self._extract_features(text)
        questions = [
            "What's the target launch timeframe (rough)?",
            "Who are the primary users of this product?",
            "Which core features must be included (e.g. auth, payments, search, user profiles)?"
        ]

        # If integrations/features detected, ask specifics
        if any(k in ["payment", "ecommerce", "shop", "checkout", "cart"] for k in features):
            questions.append("Will payments be processed on the site? Which provider (Stripe, PayPal, other)?")
        if any(k in ["api", "integration", "crm", "hubspot"] for k in features):
            questions.append("Please list any third-party systems you must integrate with (CRM, payment, identity).")

        # content/provider question
        questions.append("Who will provide content (text/images)?")
        # budget check
        questions.append("Do you have a preferred budget range or ballpark figure?")

        # limit to 6 questions to keep flow short
        return questions[:6]

    def process_followup(self, text: str, answers: List[Dict[str, Any]], client_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Build an estimate from the original text + collected answers.
        Returns a dict in the same shape used by the frontend:
          { status: "completed", summary, estimate: { totalHours, totalCost }, sow: base64(sow_text) }
        """
        # revised heuristics
        base_hours = 40
        features = self._extract_features(text)
        feature_hours = len(features) * 12  # increased per-feature weight

        # clarity reduces uncertainty -> reduce contingency hours per answer
        clarity_reduction = len(answers) * 3

        # add more hours if integration answers list many items
        extra_integrations = 0
        for a in answers:
            q = (a.get("question") or "").lower()
            ans = (a.get("answer") or "").lower()
            if "integrat" in q or "integrat" in ans:
                extra_integrations += max(0, len([s for s in re.split(r"[,\n;]+", ans) if s.strip()]) - 1)

        integration_hours = extra_integrations * 10

        total_hours_calc = base_hours + feature_hours + integration_hours - clarity_reduction
        total_hours = int(math.ceil(max(20, total_hours_calc)))  # enforce a sensible minimum

        # updated role distribution (sums to 1.0)
        role_fracs = {
            "Software Developer": 0.50,
            "Senior Software Developer": 0.18,
            "Software Architect": 0.06,
            "WordPress Developer": 0.12,
            "Project Manager": 0.08,
            "Cloud Architect / DevOps Engineer": 0.06
        }

        rate_card = self.get_rate_card()  # role->rate mapping
        # Ensure all canonical roles exist in rate_card
        for role in role_fracs.keys():
            if role not in rate_card:
                rate_card[role] = 90.0

        # calculate cost per role
        breakdown = {}
        total_cost = 0.0
        for role, frac in role_fracs.items():
            hrs = int(round(total_hours * frac))
            rate = float(rate_card.get(role, 90.0))
            cost = round(hrs * rate, 2)
            breakdown[role] = {"hours": hrs, "rate": rate, "cost": cost}
            total_cost += cost

        # Build a simple SOW text
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

        sow_text = "\n".join(sow_lines)
        sow_b64 = base64.b64encode(sow_text.encode("utf-8")).decode("utf-8")

        # persist SOW to knowledge base lightly
        try:
            parsed = {"features": features, "final_price": total_cost}
            self.ingest_sow(parsed, {"name": f"generated-{int(datetime.utcnow().timestamp())}.txt"})
        except Exception:
            pass

        return {
            "status": "completed",
            "summary": f"Estimated {total_hours} hours, ${round(total_cost,2)} total.",
            "estimate": {"totalHours": total_hours, "totalCost": round(total_cost, 2), "breakdown": breakdown},
            "sow": sow_b64
        }

    def process_client_input(self, text: str, client_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Entry point used by /api/message when no answers provided.
        Return clarifying questions or immediate estimate if description is very specific.
        """
        # If description is lengthy and mentions price/budget, produce a quick estimate
        if isinstance(text, str) and (len(text) > 400 or re.search(r"\$(\d+)", text) or "budget" in text.lower()):
            # create a short estimate with no clarifying questions
            return self.process_followup(text, [], client_info or {})
        # otherwise list clarifying questions
        qs = self.generate_clarifying_questions(text, client_info)
        return {"requires_clarification": True, "questions": qs}

    def get_rate_card(self) -> Dict[str, float]:
        try:
            return self.rate_store.get_rate_card() or {}
        except Exception:
            # fallback canonical card
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
            # restrict to canonical roles — ignore unexpected extra roles to keep consistency
            canonical = {
                "Software Developer",
                "Senior Software Developer",
                "Software Architect",
                "WordPress Developer",
                "Project Manager",
                "Cloud Architect / DevOps Engineer"
            }
            # filter and upsert
            filtered = {r: float(new_card[r]) for r in new_card if r in canonical}
            if filtered:
                self.rate_store.update_rate_card(filtered)
        except Exception:
            # swallow errors — db fallback handled by caller
            pass

    def ingest_sow(self, parsed: Dict[str, Any], metadata: Dict[str, Any]):
        try:
            self.sow_store.insert(parsed, metadata)
        except Exception:
            pass