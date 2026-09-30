# Metric-learning track

Visual retrieval over a confirmed-product gallery, and what survived contact
with evaluation.

## Fine-tuned ArcFace for shelf retrieval

Studio packshots and shelf photos live in different visual worlds; retrieval
from packshot galleries suffered badly. A **fine-tuned ArcFace metric-learning
model** closed most of that packshot→shelf gap: cross-store
**Recall@1 84.1%** against **26.4%** for the DINOv2 baseline on the audited
benchmark.

It was rolled out in stages: shadow voting alongside the live DINOv2 KNN first,
then a stage-1 rollout running in parallel with DINOv2.

## The re-ranking variant that measured worse — and was killed

A re-ranking variant looked promising in aggregate but **inverted accuracy on
disputed cases** — exactly the cases it existed for. It was not shipped.
Negative results are acted on, not archived.

## Package type: three mechanisms, none of them global

Package type (canister vs PET bottle vs bucket vs carton) is resolved by three
separate, independently gated mechanisms:

- **A VLM package-type question** — the vision model reads the package from the
  crop, and a SKU is assigned only when exactly one candidate in the family
  carries that package. Audit precision **92.7%**; per-form accuracy on **401
  crops** was **93% for PET** and **93% for bucket**. Canister families are
  **excluded** from this path — canister accuracy was only **57%**, most of the
  error leaking to PET.
- **A small calibrated head on DINOv2 embeddings** (linear SVC with Platt
  calibration) for the canister-vs-bottle confusion, run in **shadow** behind a
  per-family allowlist rather than as a global change.
- **Box aspect-ratio geometry** for 930 g vs 1900 g canisters — **AUC
  0.89–0.90**, accuracy **92.4% / 90.8%** on **n = 181**. Relative height alone
  had measured **AUC 0.53**: the same idea on the wrong feature.

## Gallery quality doctrine

Only crops whose **visual appearance** unambiguously identifies the SKU may
enter the reference gallery. A correctly-labeled crop that is visually
identical to a sibling SKU (same film, different weight) is a *harmful*
reference — it retrieves its siblings and spreads confusion. Such SKU families
are excluded from the gallery track by design and resolved at brand+type tier.
