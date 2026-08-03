# Metric-learning track

Visual retrieval over a confirmed-product gallery, and what survived contact
with evaluation.

## ArcFace head over frozen embeddings

Studio packshots and shelf photos live in different visual worlds; retrieval
from packshot galleries suffered badly. An **ArcFace head trained on frozen
visual embeddings** closed most of that packshot→shelf gap:
**R@1 ~19% → ~75%** on the held-out split.

## The re-ranking variant that measured worse — and was killed

A re-ranking variant looked promising in aggregate but **inverted accuracy on
disputed cases** — exactly the cases it existed for. It was not shipped.
Negative results are acted on, not archived.

## A dedicated head for one confusion

A long-standing canister-vs-bottle confusion was solved by a small calibrated
head on visual embeddings: recall on the class went **~14% → mid-90s** at high
precision, promoted behind a validated per-family allowlist — narrow, named
scope instead of a global change.

## Gallery quality doctrine

Only crops whose **visual appearance** unambiguously identifies the SKU may
enter the reference gallery. A correctly-labeled crop that is visually
identical to a sibling SKU (same film, different weight) is a *harmful*
reference — it retrieves its siblings and spreads confusion. Such SKU families
are excluded from the gallery track by design and resolved at brand+type tier.
