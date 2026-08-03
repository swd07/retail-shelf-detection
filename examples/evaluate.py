#!/usr/bin/env python3
"""Evaluation harness demo: honest metrics for a shelf pipeline.

Two things this script demonstrates, both learned in production:

  1. Metrics that respect abstention. A pipeline that may answer "Unknown"
     needs precision / recall / F1 *and* abstention rate reported together —
     otherwise abstaining looks like failure (it is not; it is the design).

  2. Grouped-by-image splits. One shelf photo yields many correlated crops
     (same lighting, same camera, same facing pattern). A naive random split
     leaks that correlation between train and test and INFLATES the metric.
     Splitting by image id removes the leak. This script builds a synthetic
     dataset with within-image correlation and shows the gap.

Run:  python3 examples/evaluate.py     (stdlib only, Python 3.10+)
"""
from __future__ import annotations

import random
from dataclasses import dataclass

random.seed(7)  # deterministic demo

BRANDS = ["ALPINA", "GORYANKA", "VIOLETTE", "NOVAYA"]


@dataclass
class LabeledCrop:
    image_id: int
    true_brand: str
    predicted: str | None       # None = the pipeline abstained ("Unknown")


# --- metrics ------------------------------------------------------------------

def metrics(crops: list[LabeledCrop]) -> dict[str, float]:
    answered = [c for c in crops if c.predicted is not None]
    correct = sum(1 for c in answered if c.predicted == c.true_brand)
    precision = correct / len(answered) if answered else 0.0
    recall = correct / len(crops) if crops else 0.0          # vs ALL crops
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "abstention_rate": 1 - len(answered) / len(crops) if crops else 0.0,
    }


# --- synthetic dataset with within-image correlation --------------------------

def make_dataset(n_images: int = 60, crops_per_image: int = 12) -> list[LabeledCrop]:
    """Each image gets a quality factor; every crop in it inherits that factor.

    That is exactly the correlation a naive split leaks: two crops of one photo
    are far more alike than two crops of different photos.
    """
    data: list[LabeledCrop] = []
    for img in range(n_images):
        image_quality = random.uniform(0.45, 0.95)   # blur/light of THIS photo
        for _ in range(crops_per_image):
            true = random.choice(BRANDS)
            p_correct = image_quality                # crop accuracy ~ image quality
            r = random.random()
            if r < p_correct:
                pred: str | None = true
            elif r < p_correct + 0.15:
                pred = None                          # honest abstention
            else:
                pred = random.choice([b for b in BRANDS if b != true])
            data.append(LabeledCrop(img, true, pred))
    return data


# --- the split experiment -----------------------------------------------------

def naive_split(data: list[LabeledCrop], test_frac: float = 0.3):
    """Random split by CROP — leaks image identity between train and test."""
    shuffled = random.sample(data, len(data))
    cut = int(len(shuffled) * test_frac)
    return shuffled[cut:], shuffled[:cut]


def grouped_split(data: list[LabeledCrop], test_frac: float = 0.3):
    """Split by IMAGE — a photo is entirely in train or entirely in test."""
    ids = sorted({c.image_id for c in data})
    test_ids = set(random.sample(ids, int(len(ids) * test_frac)))
    train = [c for c in data if c.image_id not in test_ids]
    test = [c for c in data if c.image_id in test_ids]
    return train, test


def calibration_gap(train: list[LabeledCrop], test: list[LabeledCrop]) -> float:
    """|train F1 - test F1|: how much the split lets you fool yourself.

    With leakage the two halves look interchangeable (tiny gap -> overconfident
    threshold tuning). With grouped split the gap is honest.
    """
    return abs(metrics(train)["f1"] - metrics(test)["f1"])


def main() -> None:
    data = make_dataset()
    m = metrics(data)
    print("population metrics (all crops):")
    for k, v in m.items():
        print(f"  {k:<16} {v:.3f}")

    print("\nsplit experiment (30% test, 20 runs each):")
    for name, splitter in (("naive by-crop", naive_split), ("grouped by-image", grouped_split)):
        gaps = []
        for _ in range(20):
            train, test = splitter(data)
            gaps.append(calibration_gap(train, test))
        avg = sum(gaps) / len(gaps)
        print(f"  {name:<18} avg |train F1 - test F1| = {avg:.3f}")

    print(
        "\nreading: the naive split makes train and test look interchangeable —\n"
        "any threshold tuned on it will overfit silently. The grouped split\n"
        "shows the real image-to-image variance you will meet in production.\n"
        "In our production system this exact effect was measured as a resolver\n"
        "scoring 98% on a curated subset and ~82% on the full population."
    )


if __name__ == "__main__":
    main()
