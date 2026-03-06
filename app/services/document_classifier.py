"""Document classification: rule-based + AI fallback."""

import re
from app.core.logging import log

# Keyword patterns per document type
_TYPE_PATTERNS = {
    "contract": {
        "filename": re.compile(r"(contract|agreement|msa|service.agreement)", re.I),
        "keywords": [
            "this agreement", "service agreement", "master agreement",
            "hereby agrees", "terms and conditions", "governing law",
            "effective date", "term of", "termination",
        ],
    },
    "nda": {
        "filename": re.compile(r"(nda|non.?disclosure|confidential)", re.I),
        "keywords": [
            "non-disclosure", "confidential information", "nda",
            "disclosing party", "receiving party", "confidentiality",
        ],
    },
    "purchase_annex": {
        "filename": re.compile(r"(annex|addendum|amendment|sla|purchase)", re.I),
        "keywords": [
            "annex to", "addendum", "amendment", "purchase order",
            "service level", "sla", "pricing annex",
        ],
    },
    "commercial_offer": {
        "filename": re.compile(r"(offer|proposal|quote|quotation|rfp)", re.I),
        "keywords": [
            "commercial offer", "proposal", "quotation", "quote",
            "we are pleased to", "executive summary", "investment overview",
        ],
    },
}


def classify_by_rules(filename: str, text: str) -> tuple[str, float]:
    """Rule-based classification. Returns (doc_type, confidence)."""
    text_lower = text.lower()
    scores: dict[str, float] = {}

    for doc_type, patterns in _TYPE_PATTERNS.items():
        score = 0.0
        # Filename match (strong signal)
        if patterns["filename"].search(filename):
            score += 0.5

        # Keyword density
        keyword_hits = sum(1 for kw in patterns["keywords"] if kw in text_lower)
        keyword_ratio = keyword_hits / len(patterns["keywords"]) if patterns["keywords"] else 0
        score += keyword_ratio * 0.5

        scores[doc_type] = score

    if not scores:
        return "other", 0.1

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    if best_score < 0.15:
        return "other", 0.3

    return best_type, min(best_score, 1.0)


async def classify_document(filename: str, text: str) -> tuple[str, float]:
    """Classify document type. Uses rules first, AI for ambiguous cases."""
    doc_type, confidence = classify_by_rules(filename, text)

    if confidence >= 0.5:
        return doc_type, confidence

    # AI fallback for ambiguous cases
    if text.strip():
        try:
            from app.integrations.llm_router import get_llm_router
            router = get_llm_router()
            system = (
                "You are a document classifier. Classify the document into exactly one of these types: "
                "contract, nda, purchase_annex, commercial_offer, other. "
                "Respond with ONLY the type name, nothing else."
            )
            snippet = text[:3000]
            user_prompt = f"Filename: {filename}\n\nDocument text (first 3000 chars):\n{snippet}"
            result = await router.generate(system, user_prompt, max_tokens=20)
            ai_type = result.strip().lower().replace(" ", "_")

            valid_types = {"contract", "nda", "purchase_annex", "commercial_offer", "other"}
            if ai_type in valid_types:
                return ai_type, max(confidence, 0.6)
        except Exception as e:
            log.warning("ai_classification_failed", error=str(e))

    return doc_type, confidence
