# Retail Shelf Detection — Share-of-Shelf Computer Vision Pipeline

> Production CV pipeline that turns retail shelf photos into **share-of-shelf**,
> **SKU recognition / assortment**, and price-tag analytics. Case study of a live system:
> architecture, guardrails, honest metrics (detection F1 0.68 → 0.91), and the evaluation
> discipline that keeps it honest.

**Keywords:** shelf detection · share of shelf · SKU recognition · planogram · retail analytics ·
merchandising computer vision · YOLO · DINOv2 · Qdrant · vision-language OCR


![Live pipeline output: detected packs, brand/SKU labels, price tags, and honest "unknown" abstentions on a real store shelf](assets/shelf-detection-live.jpg)

*Live output on a real shelf: product boxes with brand/SKU labels, price-tag detections with read prices, and explicit `unknown` abstentions where evidence is insufficient — the honest-Unknown design below, visible in production.*

## Problem

Measure on-shelf reality at scale, directly from photos:

- **share of shelf** (own brand vs. competitors),
- **assortment coverage** (which SKUs are present),
- **package/format and size mix**,

without manual tagging, and accurately enough to drive business decisions. The hard constraint:
an **honest** number. A pipeline that confidently mislabels competitor packs as own product
inflates the headline metric - so abstaining ("Unknown") is preferable to a confident wrong
answer.

## Business impact

- Automated shelf analysis at production scale: ~300k product boxes per month across ~120 shelf installations.
- Provided measurable share-of-shelf, assortment coverage, competitor presence, and package-format analytics from field photos.
- Reduced dependence on manual shelf tagging while preserving trustworthy metrics through explicit Unknown classifications.

## Architecture

![Shelf detection CV pipeline](assets/shelf-detection-pipeline.png)

A staged, asynchronous pipeline with self-hosted GPU inference:

```
mobile capture app
   → ingestion API → durable work queue → async worker
        → object detection (YOLO / open-vocabulary)         # localize packs
        → OCR + Vision-Language model                       # read brand/label text
        → visual embeddings (DINOv2 ViT-L/14)               # KNN over a confirmed-product gallery
        → retrieval-augmented matching (vector DB: Qdrant)  # SKU identification
        → rule-based fusion + guardrail layer               # combine signals, abstain when unsure
        → metrics (share of shelf, assortment, coverage)
```

- **Detection:** YOLO and open-vocabulary detection localize product packs; a dedup stage removes
  contained/overlapping/duplicate boxes and shelf-band false positives.
- **OCR / VLM:** each crop is read by a Vision-Language OCR model; brand tokens are matched
  against a normalized brand vocabulary.
- **Embeddings + retrieval:** DINOv2 visual embeddings feed a KNN gallery of confirmed products;
  in parallel, retrieval over a **Qdrant** vector database provides SKU candidates.
- **Fusion + guardrails:** a rule-based layer fuses OCR / retrieval / visual evidence with an
  explicit priority order, and a set of guardrails reject or relabel low-evidence matches. A
  geometry-based *within-shelf* resolver disambiguates same-brand siblings (e.g. weight/format
  variants) using bounding-box layout when the label text is unreadable.
- **Hybrid reporting tier:** share-of-shelf is reported at **brand+type** level by default;
  SKU-level detail only where variant evidence actually exists (own brands + key competitors).
  Same-brand *twins* - visually identical packaging across weights/flavors - are handled
  honestly: the pipeline reports the brand and marks the variant as undetermined instead of
  guessing (our OCR pipeline found an explicit weight token in only 5.6% of 39,253
  variant-ambiguous crops over a 30-day window).
- **GPU inference:** detection, embeddings, OCR, and the VLM run on a self-hosted **NVIDIA H200**.

## My role

I designed and built the **entire pipeline**: detector integration and dedup, the OCR/VLM and
embedding services, the retrieval/matching layer, the fusion and guardrail logic, the within-shelf
geometric resolver, the training/evaluation harness, and the catalog-normalization tooling. I used
LLMs as a **teacher/auditor** for label adjudication and dataset construction - never as
uncontrolled production inference.

## Stack

`PyTorch` · `YOLO / open-vocabulary detection` · `DINOv2` · `Vision-Language OCR` · `vector retrieval` · `KNN matching` · `Qdrant` · `ArcFace metric learning` · `FastAPI` · `PostgreSQL` · `self-hosted S3-compatible object
storage` · `Docker` · `NVIDIA H200 GPU inference`

## Results

- **1,200+ SKU catalog**, 14k confirmed-crop visual gallery feeding the KNN track.
- **Detection F1: 0.68 → 0.91 on unseen (out-of-sample) photos.**
- **Catalog normalization: 34 → 20 categories** - collapsing duplicated/ambiguous classes that
  were degrading matching.
- **~300 false positives eliminated** via a targeted regex/normalization fix in the label path.
- **Package classifier ~92% overall accuracy**, evaluated leak-free with grouped-by-image splits
  and cross-store stress tests (one photo can contain many correlated crops, so naive splits leak).
- Solved a long-standing **canister-vs-bottle** confusion by training a dedicated calibrated head
  on visual embeddings, lifting recall on that class from ~14% to the mid-90s while holding high
  precision - promoted to production behind a validated allowlist.


## Engineering highlights

- **Honest-Unknown design:** guardrails explicitly abstain; I quantified that a large share of
  "Unknown" boxes were *intentional competitor rejections*, not coverage gaps - important context
  for interpreting the headline metric correctly.
- **Pre-registered gates:** acceptance thresholds are written and committed *before* the
  evaluation page is opened - per-stratum thresholds and stop-rules ("any false admission on
  an own product reverts the whole package"), making reviews anchoring-proof.


## Runnable examples

No production code is published, but the *decision logic shape* and the evaluation
discipline are runnable (stdlib only, Python 3.10+):

```
python3 examples/fusion_demo.py   # fusion + abstaining guardrails on synthetic crops
python3 examples/evaluate.py      # precision/recall/F1 + abstention rate; grouped-by-image splits
```

`fusion_demo.py` walks six synthetic crops through the priority-ordered fusion and
prints which rule decided each - including the three abstention paths. `evaluate.py`
shows why metrics must report abstention explicitly and why naive random splits
overstate accuracy on correlated shelf crops.

## Deep dives

- [Expert-readability ceiling](docs/human-ceiling.md) - the pre-registered protocol, the 31.6% + 68.4% x 65.5% = 76.4% arithmetic, interval method, limitations
- [Evaluation honesty](docs/evaluation.md) - population-level validation, grouped splits
- [Production lessons](docs/production-lessons.md) - shadow rollouts, pre-registered gates, config drift made impossible
- [Metric learning](docs/metric-learning.md) - ArcFace packshot→shelf (R@1 19%→75%), the re-ranker that was killed, gallery doctrine

---

## About

This is a case-study repository for a **production** system I built and operate end-to-end as the
sole engineer (code is private — it runs inside a commercial environment).

- Full portfolio with more case studies: **[ai-platform-portfolio](https://github.com/swd07/ai-platform-portfolio)**
- Author: **Eduard Kharaev** — [profile](https://github.com/swd07) · haraev87@gmail.com · TG [@Edharaev](https://t.me/Edharaev)
