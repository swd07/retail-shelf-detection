#!/usr/bin/env python3
"""Synthetic demo of the fusion + guardrail layer used in the shelf pipeline.

This is NOT production code and contains NO production data. It reproduces the
*decision logic shape* on hand-built synthetic crops so the design is inspectable
and runnable:

  1. Evidence fusion with an explicit priority order
     (OCR-brand + visual > OCR-brand + retrieval > strong retrieval > visual consensus).
  2. Guardrails that ABSTAIN instead of guessing:
     - a competitor brand assignment requires an explicit OCR brand token;
     - generic OCR ("MILK", "CHEESE") never confirms an identity on its own;
     - same-brand weight twins with no readable weight resolve to the brand tier,
       never to a guessed SKU.

Run:  python3 examples/fusion_demo.py     (stdlib only, Python 3.10+)
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# --- tiny synthetic "catalog" -------------------------------------------------

OWN_BRANDS = {"ALPINA"}                      # our product line
BRAND_TOKENS = {                             # OCR evidence vocabulary per brand
    "ALPINA": {"ALPINA"},
    "GORYANKA": {"GORYANKA"},
    "VIOLETTE": {"VIOLETTE"},
}
GENERIC_OCR = {"MILK", "CHEESE", "BUTTER", "SOUR CREAM", "100%"}  # never evidence
WEIGHT_TWINS = {                             # same brand+type, different weight only
    ("ALPINA", "yogurt"): ["ALPINA-YOG-430", "ALPINA-YOG-870"],
}

RAG_STRONG = 0.55        # retrieval score accepted on its own
KNN_MIN_VOTES = 3        # of 5 gallery neighbours
KNN_MAX_DIST = 0.34


@dataclass
class Crop:
    """Signals the upstream stages produce for one detected pack."""
    name: str
    ocr_text: str
    rag_candidate: str | None   # SKU proposed by vector retrieval
    rag_brand: str | None
    rag_score: float
    knn_brand_votes: list[str]  # brand of each of the 5 nearest gallery crops
    knn_distance: float         # distance to the nearest neighbour
    category: str = "yogurt"


@dataclass
class Decision:
    brand: str | None
    sku: str | None
    path: str                   # which rule decided — kept for audit, always
    note: str = ""


def ocr_brand(text: str) -> str | None:
    up = text.upper()
    for brand, tokens in BRAND_TOKENS.items():
        if any(t in up for t in tokens):
            return brand
    return None


def ocr_is_generic(text: str) -> bool:
    up = " ".join(w for w in text.upper().split())
    informative = [w for w in up.split() if w not in GENERIC_OCR and not w.rstrip("%").isdigit()]
    return not informative


def knn_consensus(crop: Crop) -> str | None:
    top = max(set(crop.knn_brand_votes), key=crop.knn_brand_votes.count)
    votes = crop.knn_brand_votes.count(top)
    if votes >= KNN_MIN_VOTES and crop.knn_distance <= KNN_MAX_DIST:
        return top
    return None


def weight_readable(text: str) -> bool:
    """A digit followed by a unit — not just a unit letter inside a word."""
    return bool(re.search(r"\d\s*(G|ML|KG|L|Г|МЛ|КГ)\b", text.upper()))


def fuse(crop: Crop) -> Decision:
    """Priority-ordered fusion with abstaining guardrails."""
    o_brand = ocr_brand(crop.ocr_text)
    v_brand = knn_consensus(crop)

    # -- fusion, strongest evidence first ------------------------------------
    if o_brand and v_brand == o_brand:
        brand, path = o_brand, "ocr_brand+visual"
    elif o_brand and crop.rag_brand == o_brand:
        brand, path = o_brand, "ocr_brand+retrieval"
    elif crop.rag_score >= RAG_STRONG and crop.rag_brand:
        brand, path = crop.rag_brand, "retrieval_strong"
    elif v_brand:
        brand, path = v_brand, "visual_consensus"
    else:
        return Decision(None, None, "unknown", "no evidence agrees")

    # -- guardrail 1: competitor needs explicit OCR evidence -----------------
    if brand not in OWN_BRANDS and ocr_brand(crop.ocr_text) != brand:
        return Decision(None, None, "rejected_competitor_without_brand_evidence",
                        f"visual/retrieval said {brand}, OCR shows no token for it")

    # -- guardrail 2: generic OCR alone never confirms an SKU ----------------
    if ocr_is_generic(crop.ocr_text) and path.startswith("retrieval"):
        return Decision(None, None, "rejected_generic_ocr",
                        "retrieval matched, but OCR is category words only")

    # -- guardrail 3: weight twins resolve to brand tier, never a guess ------
    twins = WEIGHT_TWINS.get((brand, crop.category), [])
    if len(twins) > 1 and not weight_readable(crop.ocr_text):
        return Decision(brand, None, "ambiguous_sibling_weight",
                        f"{len(twins)} weight variants, none readable -> brand tier")

    sku = crop.rag_candidate if crop.rag_brand == brand else None
    return Decision(brand, sku, path)


DEMO = [
    Crop("clean own pack", "ALPINA YOGURT 430G", "ALPINA-YOG-430", "ALPINA", 0.82,
         ["ALPINA"] * 4 + ["GORYANKA"], 0.11),
    Crop("own pack, weight unreadable", "ALPINA YOGURT", "ALPINA-YOG-430", "ALPINA", 0.78,
         ["ALPINA"] * 5, 0.09),
    Crop("competitor, OCR confirms", "GORYANKA SOUR CREAM 20%", "GOR-SC-700", "GORYANKA", 0.71,
         ["GORYANKA"] * 3 + ["ALPINA"] * 2, 0.18),
    Crop("competitor, OCR garbled", "S0UR CRE4M", "GOR-SC-700", "GORYANKA", 0.66,
         ["GORYANKA"] * 5, 0.12),
    Crop("generic OCR only", "MILK 100%", "ALPINA-YOG-430", "ALPINA", 0.61,
         ["ALPINA", "GORYANKA", "VIOLETTE", "GORYANKA", "NOVAYA"], 0.29),
    Crop("blurry nothing", "", None, None, 0.20,
         ["ALPINA", "GORYANKA", "VIOLETTE", "GORYANKA", "ALPINA"], 0.41),
]


def main() -> None:
    w = max(len(c.name) for c in DEMO)
    abstained = 0
    for crop in DEMO:
        d = fuse(crop)
        verdict = f"{d.brand or 'UNKNOWN'}" + (f" / {d.sku}" if d.sku else "")
        if d.brand is None or d.sku is None:
            abstained += 1
        print(f"{crop.name:<{w}}  ->  {verdict:<22} [{d.path}]" + (f"  {d.note}" if d.note else ""))
    print(f"\nabstained (fully or to brand tier): {abstained}/{len(DEMO)} — "
          "abstaining beats a confident wrong answer.")


if __name__ == "__main__":
    main()
