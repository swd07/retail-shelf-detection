# Measuring an expert-readability ceiling for shelf recognition

A technical note on one measurement that changed our roadmap more than any model
improvement in the same quarter. Part of the [retail shelf detection case study](../README.md).

## The question

Our production pipeline turns retail shelf photos into share-of-shelf analytics
(~300k detected packs/month). Like every system of this kind it has a long tail
of "Unknown" boxes. Every planning conversation circled the same question:
**how much of that tail is our engineering debt, and how much is unreadable data?**

Rather than guess, we measured what a motivated human expert can read.

## Protocol

Pre-registered: the sampling rule and decision criteria were written down and
committed **before** any crop was viewed.

- **Population:** all product crops the production pipeline could *not* identify
  (a 30-day window).
- **Sample:** 120 crops drawn uniformly at random from that population.
- **Blind reading:** a single domain expert viewed each crop with no model
  output and **no candidate list**. (We had previously measured that showing
  candidate suggestions to a reader produces hallucinated confirmations, so the
  reader gets pixels only.)
- **Task:** name the brand, or mark the crop unreadable. Zooming into the
  full-resolution crop was allowed; external context was not.

## Result and the arithmetic

The expert read the brand on **65.5%** of the sampled unrecognized crops.

At measurement time the pipeline already identified **31.6%** of all boxes.
The remaining **68.4%** is the tail the sample was drawn from, so the estimated
ceiling for brand recognition is:

```
31.6% + 68.4% x 65.5% = 76.4%
```

**Interval:** the 95% Wald interval on the 65.5% read-rate with n = 120 is
+-8.5 percentage points; scaled by the 68.4% unrecognized share this gives an
approximate 95% interval of **+-5.8 pp** on the ceiling estimate (a Wilson
interval gives a similar width). The interval treats the 120 reads as
independent Bernoulli trials — see limitations.

## What changed downstream

- **Performance restated as a share of the ceiling.** At measurement time the
  pipeline sat at 41.3% of what the expert could do — a far more honest number
  than any absolute accuracy, because it separates "the model is behind" from
  "the data ends here".
- **Most of the remaining gap turned out to be a catalog-boundary question** —
  whole categories (ice cream, sauces, imported goods) deliberately not
  cataloged yet. Several planned "model improvement" projects could not have
  moved the number at all; they were cancelled before a week was spent on each.
- **Abstention was legitimized as a correct final answer.** Same-brand packages
  differing only by weight are often visually identical; our OCR pipeline found
  an explicit weight token in only **5.6% of 39,253** variant-ambiguous crops
  (30-day window). The pipeline now reports the brand and marks the variant
  undetermined instead of guessing.

## Limitations, named up front

1. **Single expert.** This is a *single-expert readability estimate under this
   protocol*, not an inter-annotator-agreement study. The expert knows the
   assortment well, so the estimate is closer to an upper bound of motivated
   human performance than to an average reader.
2. **Readability, not verified correctness.** For crops the pipeline cannot
   identify there is no independent ground truth; a confident expert reading is
   itself the best available label. Reads were conservative by protocol
   (uncertain = unreadable), which biases the ceiling *downward* if anything.
3. **Correlated sample.** The 120 crops come from real shelf photos; several
   crops can share a photo or a store, so the effective sample size is somewhat
   below 120 and the stated interval is optimistic. We did not correct for
   this clustering.
4. **Extrapolation step.** Scaling the sample read-rate to the full tail
   assumes the uniform sample represents the tail's composition; the tail
   drifts as stores and seasons change, so the ceiling is a snapshot, not a
   constant.
5. **Expert-readable is not the same as model-achievable** — in either
   direction. A model can use non-text cues the reader ignores; the reader may
   use packaging gestalt no current model captures.
6. We also measured a brand+package-type readability figure, but its
   denominator definition does not compress into one honest sentence, so it is
   omitted here rather than risk ambiguity.

## Reproduce the evaluation discipline

The repo ships runnable, stdlib-only examples of the surrounding methodology:
[`examples/evaluate.py`](../examples/evaluate.py) (metrics with an explicit
abstention rate; why naive random splits overstate accuracy on correlated shelf
crops) and [`examples/fusion_demo.py`](../examples/fusion_demo.py) (the
abstaining guardrail logic).

Criticism of the protocol is welcome — in particular the extrapolation step and
the independence assumption behind the interval.
