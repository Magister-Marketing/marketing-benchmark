"""Small statistical helpers with no third-party dependency."""

from __future__ import annotations

import math
from typing import Iterable


def mean(values: Iterable[float]) -> float | None:
    rows = list(values)
    return sum(rows) / len(rows) if rows else None


def percentile(values: Iterable[float], percentile_value: float) -> float | None:
    rows = sorted(values)
    if not rows:
        return None
    if not 0 <= percentile_value <= 1:
        raise ValueError("percentile must be between 0 and 1")
    index = (len(rows) - 1) * percentile_value
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return rows[lower]
    return rows[lower] + (rows[upper] - rows[lower]) * (index - lower)


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return (0.0, 0.0)
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(
            proportion * (1 - proportion) / total + z * z / (4 * total * total)
        )
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)
