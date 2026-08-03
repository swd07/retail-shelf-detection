# Evaluation honesty

How this pipeline is measured, and the two lessons that shaped the process.

## Population-level validation, always

A resolver that measured **98% on a curated subset dropped to ~82% on the full
population**. Curated subsets over-represent clean, canonical crops; production
is dominated by glare, occlusion and odd angles. Since then no change is
promoted on subset numbers — validation runs on the full population, before any
production change.

## Grouped-by-image splits

One shelf photo yields many correlated crops (same lighting, camera, facing
pattern). A naive random split leaks that correlation between train and test
and silently inflates the metric. All splits are **grouped by image id**.
A runnable demonstration: [`examples/evaluate.py`](../examples/evaluate.py).

## The human-ceiling benchmark

The strongest evaluation question is not "how accurate is the model" but
"how much of the *achievable* is achieved". A blind protocol — thresholds and
sample pre-registered before viewing — measured the **human** brand-readability
ceiling on unrecognized boxes at **76.4%**: on a quarter of real shelf crops a
human cannot read the brand either.

Expressing pipeline performance as a **percentage of that ceiling** reframed
the roadmap: the remaining gap turned out to be a *catalog-boundary* question
(categories deliberately out of scope), not engineering debt. That
reframing killed several would-be "improvement" projects that could not have
moved the number.
