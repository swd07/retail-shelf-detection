# Retail Shelf Detection — Production Retrieval & Multimodal Shelf Intelligence

> Technical case-study repository for a live merchandising AI subsystem: offline field capture,
> detection, OCR/VLM, dense retrieval, visual metric learning, deterministic fusion, guardrails,
> evaluation and gated production rollout.

**Portfolio overview:** [ai-platform-portfolio](https://github.com/swd07/ai-platform-portfolio)  
**Parent product:** [AI Chaban2 — commercial operating platform](https://github.com/swd07/ai-platform-portfolio/blob/master/projects/chaban.md)  
**Field-product deep dive:** [Offline Merchandising Terminal](https://github.com/swd07/ai-platform-portfolio/blob/master/projects/merch-terminal.md)

![Live pipeline output: detected packs, brand/SKU labels, price tags, and explicit unknown abstentions](assets/shelf-detection-live.jpg)

*Real shelf output: localized packs, brand/SKU labels, price-tag reads and explicit `unknown`
when the evidence is not strong enough.*

---

## Status

This is **production engineering with a pilot business rollout**.

- **6,145+ shelf photos** processed in the merchandising subsystem.
- **5,882 completed analyses** in the audited production queue.
- Current rollout: **40 retail outlets / 3 merchandising users**.
- **~320k OCR calls** processed by the production service.
- **~108k ArcFace shadow evaluations** recorded.

The engineering pipeline is live; the organizational rollout is still intentionally limited.

---

## Problem

A shelf photo has to become trustworthy commercial data:

- **share of shelf** — own brand vs competitors;
- **assortment coverage** — which brands/SKUs are present;
- **package / format / size mix**;
- **price-tag evidence**;
- inputs for merchandising review and execution analytics.

The difficult cases are not obvious detections. They are visually similar sibling products that
differ only by weight, fat percentage, flavour, label detail or package format.

For this problem, a confident wrong own-vs-competitor decision is worse than returning
`unknown`. The system is therefore designed around **evidence, abstention and reproducible
post-mortems**, not maximum forced coverage.

There is also a non-model problem: retail capture happens under weak connectivity, app interruption
and device restarts. A model pipeline is not production-ready if the field user cannot reliably
create and synchronize the input data.

---

## End-to-end production architecture

```text
Native Android field terminal
  → Room-backed durable photo queue
  → network-aware WorkManager synchronization
  → ingest API
  → object storage + durable analysis queue
  → async analysis worker
  → GroundingDINO detection
  → Qwen2.5-VL OCR / package reading
  → Qwen3-Embedding-8B
  → Qdrant dense text retrieval
  → attribute-aware reranking
  → DINOv2 visual k-NN
  → fine-tuned ArcFace metric retrieval
  → deterministic signal fusion
  → evidence guardrails
  → SKU / brand / unknown
  → share-of-shelf / assortment / competitor analytics
```

The production AI stack is self-hosted on owned NVIDIA H200 infrastructure.

The LLM **does not choose the final SKU**. It extracts textual and package evidence; the final
identity is selected by a deterministic decision layer that combines independent retrieval and
visual signals.

---

## Field product — offline-first Android terminal

The merchandising terminal is a native **Kotlin / Jetpack Compose** application built for actual
store conditions rather than a thin camera screen.

### Durable work before upload

Captured photos enter a **Room-backed local queue** with the shelf/display and capture context needed
for delayed delivery. The field user can keep working before the network request or GPU analysis
finishes.

The queue supports:

- pending / upload / failure state visible to the user;
- per-photo retry and delete;
- bulk send;
- periodic synchronization through **WorkManager**;
- immediate retry when connectivity changes from offline to online;
- recovery of records left in an in-flight state after process/device interruption.

The recovery path is important: a mobile process can die mid-upload, so `UPLOADING` cannot be treated
as an eternal terminal state.

### Offline shelf registry

Later iterations moved more than the media queue offline. The application caches the shelf/display
registry in Room and can fall back to the local copy when the API is unavailable. Cover images use
disk caching and can be pre-warmed after connectivity returns.

Actions that require authoritative server state are explicitly guarded while offline rather than
pretending every mutation succeeded locally.

### Analysis vs planogram mode

The same field application distinguishes normal analysis capture from **planogram** work.

A merchandiser can move through:

```text
store → shelf/display → capture → local queue → analysis
```

or:

```text
store → shelf/display → planogram image → shelf-zone annotation → sync
```

The on-device shelf-zone editor supports drawing regions over an image, dragging existing regions and
resizing them with edge/corner handles. This keeps structured correction close to the physical shelf,
where the scene is easiest to understand.

### Why this matters to the AI system

Capture, upload and inference are independent stages. Temporary store connectivity or a busy model
server does not block the merchandiser from taking the next shelf photo.

→ **[Detailed offline field-terminal case study](https://github.com/swd07/ai-platform-portfolio/blob/master/projects/merch-terminal.md)**

---

## Ingest & provenance

The ingest layer provides:

- authenticated photo upload;
- SHA-256 duplicate protection;
- object storage for media;
- durable analysis queue;
- asynchronous workers;
- production provenance linking analysis to code/config revisions.

This separates field capture from GPU inference and preserves enough context for delayed processing
and later post-mortems.

Analysis jobs run through a PostgreSQL queue using `FOR UPDATE SKIP LOCKED`, with up to 3 attempts
and automatic recovery of jobs stuck for more than 30 minutes.

---

## Detection

**GroundingDINO** localizes product regions before recognition. Earlier detector work also included
closed-set / YOLO experiments and deduplication logic for contained, overlapping and shelf-band
false-positive regions.

A separate detector track improved measured **F1 from 0.68 → 0.91 on unseen shelf photos**.

Detection is treated as one stage of the recognition system rather than the final business metric:
a good box can still become an incorrect SKU, so downstream retrieval/evidence gates remain
mandatory.

---

## OCR / VLM evidence

Each product crop is read by self-hosted **Qwen2.5-VL-72B-AWQ** served through vLLM.

The VLM extracts evidence such as:

- brand text;
- product-name fragments;
- weight / volume;
- fat percentage;
- flavour/category clues;
- package-form clues.

OCR/VLM output is evidence for retrieval and guardrails. It is not trusted as a final classifier.

---

## Dense retrieval

### Catalog representation

Each retrieval entry is represented as structured product text combining attributes such as:

`brand + name + category + subcategory + flavour + fat% + weight + volume + package_type + visual_markers`

Embeddings are produced by a self-hosted **Qwen3-Embedding-8B** service.

### Qdrant search

For each detected crop:

1. OCR/VLM produces the available text evidence.
2. The query is embedded with **Qwen3-Embedding-8B**.
3. **Qdrant** performs cosine dense retrieval.
4. Production retrieval depth is **top-20**.
5. Reliable brand evidence can activate brand-filtered candidate narrowing.
6. Candidates are reranked with structured attributes such as brand, weight, fat percentage,
   category and package evidence.

The embedding vector is **4096-dimensional and normalized**.

The production vector collection contains **1,345 retrieval entries**. The broader merchandising
catalog contains approximately **1.5k own + competitor SKUs**, so not every merchandising catalog
record is necessarily represented identically in the vector collection.

---

## Multimodal retrieval

Dense text retrieval is only one path.

In parallel, the production system uses:

- **DINOv2 ViT-L/14** for general visual embeddings and k-NN retrieval;
- a fine-tuned **ArcFace** metric-learning encoder for independent visual votes;
- OCR-derived brand and product-attribute evidence;
- package-form evidence for ambiguous families.

The working galleries are on the order of tens of thousands of confirmed/reference crops
(approximately 18.9k DINOv2 confirmed crops and 9.1k ArcFace references in the audited retrieval
configuration).

A typical decision ladder can look like:

```text
OCR brand + visual agreement
→ OCR brand + dense retrieval
→ strong dense retrieval
→ dense retrieval + independent visual support
→ visual retrieval
→ weak evidence
→ unknown
```

Every final prediction stores enough provenance — decision path, scores, thresholds and supporting
signals — to reconstruct why the system made that decision.

---

## Deterministic fusion and guardrails

The acceptance layer is deliberately conservative.

Examples of production guardrails include:

- OCR **brand verification**;
- **competitor protection** to reduce own/competitor contamination;
- retrieval-evidence gates requiring independent support for weak candidates;
- **package-form** protection for bottle / canister / carton ambiguity;
- **ArcFace rescue** when the metric-learning signal is stronger than the primary visual path;
- **price-tag / promo rejection** so non-product regions do not enter product metrics;
- sibling / weight evidence where available.

Low-evidence cases become **`unknown`** instead of being forced into a SKU.

That abstention is part of the product design: share-of-shelf and assortment numbers are only useful
if the system is allowed to say that it does not know.

---

## Evaluation as production architecture

Evaluation is not a notebook step performed after model training. It is part of the release path.

The system uses:

- human-labelled **golden sets**;
- stratification by failure mode;
- grouped / cross-store validation to reduce leakage;
- distractor and hard-negative sets;
- **Recall@1 / Recall@5** for retrieval tracks;
- FPR-anchored precision calibration;
- Wilson confidence intervals for small strata;
- pre-registered **acceptance / kill thresholds**;
- a **47k-box production replay harness** that imports the real production decision module;
- shadow tables / candidate-model telemetry;
- nightly regression checks.

Candidate changes are promoted through:

```text
off → shadow → active
```

This process has rejected rerankers and encoder replacements that looked promising locally but
weakened controlled production evaluation.

---

## Measured results

### End-to-end

- **Brand precision: 95.8%** on the confirmed end-to-end golden set.
- **SKU precision: 73.1% end-to-end**.
- Bare retrieval alone was approximately **29% SKU precision** before the full cascade,
  independent visual evidence and guardrails.

### Retrieval / metric learning

- Fine-tuned ArcFace cross-store **Recall@1: 84.1%** on the audited benchmark.
- DINOv2 baseline on the same benchmark: **26.4% Recall@1**.
- Human readability ceiling on the unresolved tail: **76.4% ± 5.8 pp** under a blind,
  pre-registered protocol.

### Production telemetry

- **~320k OCR calls** processed.
- **~108k ArcFace shadow evaluations**.
- **6k+ shelf photos** in the merchandising system.
- **5,882 completed production analyses** in the audited queue.

---

## Business outputs

Recognition results are not the end product. They feed a merchandising dashboard in the Chaban2
platform:

- **Share of shelf** — own vs competitor share by facings, per photo, store and brand; stores below
  30% own share are flagged; shelf position (top / eye / middle / bottom) is recorded.
- **SKU presence** — for each own SKU: in how many analysed stores it was found, its facings, and a
  good / warning / critical status.
- **Price intelligence from price tags** — own average shelf price vs the market, a price index,
  per-category comparison with competitor brands and price spread across stores.
- **Store markup** — shelf price vs base price per store and SKU, with a high / normal / low markup
  status.

Dashboard data is scoped by team: a manager sees only the stores of their team.

### Human-in-the-loop improvement

Low-evidence crops go to an **unknown inbox** (`new → reviewed → promoted / excluded`) together with
the crop, OCR text, visual candidates and a VLM suggestion. A reviewer assigns the product, and
promoted crops are added to the confirmed visual gallery used for DINOv2 visual re-ranking (enabled
by a feature flag). The system improves on its own failure cases without retraining a model.

### Not yet in production

Shelf zones are drawn on shelf photos in the field app, but automatic **planogram-compliance**
checking, report export and shelf alerts are on the roadmap, not in production.

---

## What this is — and is not

This is a **production retrieval-augmented recognition system embedded in a field workflow**.

It is **not** a classic document-question-answering RAG application:

- retrieved catalog candidates do not become documents for an LLM answer;
- the LLM does not generate the final SKU identity;
- there is no document-citation path in production;
- final identity comes from explainable fusion of retrieval, visual and attribute evidence.

For this business problem, deterministic fusion and calibrated abstention provide stronger control
than asking an LLM to make the final identity decision.

---

## My role

For the broader AI Chaban2 platform I was **Head of AI and Technical Owner / platform architect**: I built
the first production versions hands-on, then hired and led a team of **7 engineers** who extended them.

For this merchandising subsystem I owned the technical architecture and production rollout and was
hands-on in:

- retrieval / matching architecture;
- OCR/VLM and embedding services;
- Qdrant retrieval and attribute reranking;
- multimodal fusion and guardrails;
- golden sets, replay evaluation and kill criteria;
- metric-learning evaluation;
- production inference / rollout methodology;
- end-to-end field-to-analysis architecture and operational tooling around the pipeline.

The broader commercial platform and mobile application were extended by the team I led; this
repository focuses on this subsystem and the technical work I did on it personally.

---

## Stack

`Python` · `FastAPI` · `PyTorch` · `GroundingDINO` · `Qwen2.5-VL-72B-AWQ` ·
`Qwen3-Embedding-8B` · `Qdrant` · `DINOv2 ViT-L/14` · `ArcFace` · `vLLM` ·
`PostgreSQL` · `MinIO / S3-compatible storage` · `Kotlin` · `Jetpack Compose` ·
`Room` · `WorkManager` · `Coil` · `Docker` · `systemd / cron` · `NVIDIA H200`

---

## Runnable examples

Production code and commercial data are private, but this repository includes small runnable
examples of the **decision-logic shape and evaluation discipline**:

```bash
python3 examples/fusion_demo.py
python3 examples/evaluate.py
```

`fusion_demo.py` walks synthetic crops through priority-ordered fusion, including abstention paths.
`evaluate.py` demonstrates precision/recall/F1, abstention rate and why naive random splits can
inflate metrics on correlated shelf crops.

---

## Deep dives

- [Offline field terminal](https://github.com/swd07/ai-platform-portfolio/blob/master/projects/merch-terminal.md) — durable mobile queue, reconnect recovery, shelf cache and planogram zones.
- [Expert-readability ceiling](docs/human-ceiling.md) — blind protocol, ceiling calculation,
  intervals and limitations.
- [Evaluation honesty](docs/evaluation.md) — population-level validation and grouped splits.
- [Production lessons](docs/production-lessons.md) — shadow rollout, pre-registered gates and
  config-drift prevention.
- [Metric learning](docs/metric-learning.md) — ArcFace shelf retrieval, gallery doctrine and
  rejected candidates.

---

## Related work

- **[Full Applied AI / Solutions Architecture portfolio](https://github.com/swd07/ai-platform-portfolio)**
- **[AI Chaban2 commercial platform case study](https://github.com/swd07/ai-platform-portfolio/blob/master/projects/chaban.md)**

Author: **Eduard Kharaev** — [GitHub profile](https://github.com/swd07) ·
[haraev87@gmail.com](mailto:haraev87@gmail.com) · Telegram [@Edharaev](https://t.me/Edharaev)
