"""Versioned deterministic scorer plugin contract."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..schema import Scenario
from .contracts import GateResult


@dataclass(frozen=True)
class ScorerContext:
    repo_root: Path
    attempt_dir: Path
    attempt: dict[str, Any]
    scenario: Scenario
    events: list[dict[str, Any]]
    files: list[dict[str, Any]]
    response: str
    artifact_text: str
    environment: dict[str, Any]
    oracle: dict[str, Any]


Scorer = Callable[[ScorerContext], list[GateResult]]


class ScorerRegistry:
    def __init__(self) -> None:
        self._scorers: dict[str, Scorer] = {}

    def register(self, scorer_id: str, scorer: Scorer) -> None:
        if scorer_id in self._scorers:
            raise ValueError(f"duplicate scorer id: {scorer_id}")
        self._scorers[scorer_id] = scorer

    def run(self, scorer_ids: tuple[str, ...], context: ScorerContext) -> list[GateResult]:
        results: list[GateResult] = []
        for scorer_id in scorer_ids:
            try:
                scorer = self._scorers[scorer_id]
            except KeyError as exc:
                available = ", ".join(sorted(self._scorers)) or "none"
                raise ValueError(
                    f"unknown scorer {scorer_id!r}; registered: {available}"
                ) from exc
            results.extend(scorer(context))
        return results
