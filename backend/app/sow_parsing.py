import re

class SowParser:
    """
    Lightweight SOW parser to extract:
     - feature keywords (simple heuristics)
     - final price if mentioned
    """
    FEATURE_KEYWORDS = ["booking","appointment","ecommerce","shop","blog","auth","api","integration","reports","monitoring","ci/cd","backup"]

    def parse(self, text: str) -> dict:
        txt = text.lower()
        features = [k for k in self.FEATURE_KEYWORDS if k in txt]
        # find price patterns like $12,345 or USD 12345
        price = None
        m = re.search(r"\$[\s,]*([0-9\.,]+)", text)
        if not m:
            m = re.search(r"usd[\s:]*([0-9\.,]+)", text.lower())
        if m:
            p = m.group(1).replace(",","").strip()
            try:
                price = float(p)
            except:
                price = None
        return {"features": features, "final_price": price or 0.0}