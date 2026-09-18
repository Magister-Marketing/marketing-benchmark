"""Offline loading of separately versioned journey packs; never runs a model.

The legacy journey runner and its default SCENARIOS are deliberately unchanged.
Consumers must explicitly load a pack and snapshot its scenarios into run metadata.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

DEFAULT_PACK = Path(__file__).parent / "fixtures/journeys/usage-grounded-v1/development.json"
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]*$")


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def load_pack(path: str | Path = DEFAULT_PACK, *, allow_holdout: bool = False) -> list[dict]:
    """Return validated steps/checks scenarios, refusing holdouts by default.

    This is an accidental-use guard, not secrecy or access control. Reviewers and
    offline tests may inspect holdouts; candidates must not receive their checks.
    """
    data = json.loads(Path(path).read_text())
    expected = {"schema_version", "pack_id", "partition", "generation_status", "scenarios"}
    if not isinstance(data, dict) or set(data) != expected:
        raise ValueError("pack must contain exactly the documented metadata and scenarios")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("unsupported journey-pack schema_version")
    if not _text(data["pack_id"]) or not _IDENTIFIER.fullmatch(data["pack_id"]):
        raise ValueError("invalid pack_id")
    if data["partition"] not in ("development", "holdout"):
        raise ValueError("partition must be development or holdout")
    if data["partition"] == "holdout" and not allow_holdout:
        raise ValueError("holdout loading requires explicit allow_holdout=True")
    if data["generation_status"] != "unrun_at_authoring":
        raise ValueError("generation_status must describe the pack's unrun authoring state")
    scenarios = data["scenarios"]
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("scenarios must be a nonempty list")
    seen = set()
    for scenario in scenarios:
        if not isinstance(scenario, dict) or set(scenario) != {"id", "steps", "checks"}:
            raise ValueError("conversation scenarios must contain id, steps and checks")
        identifier = scenario["id"]
        if not _text(identifier) or not _IDENTIFIER.fullmatch(identifier) or identifier in seen:
            raise ValueError("scenario IDs must be valid and unique within a pack")
        seen.add(identifier)
        steps = scenario["steps"]
        if not isinstance(steps, list) or not steps:
            raise ValueError(f"{identifier}: steps must be a nonempty list")
        for step in steps:
            if not isinstance(step, dict) or set(step) != {"user"} or not _text(step["user"]):
                raise ValueError(f"{identifier}: each conversation step must contain nonempty user text")
        checks = scenario["checks"]
        if not isinstance(checks, dict) or not checks:
            raise ValueError(f"{identifier}: checks must be a nonempty mapping")
        if any(not _text(key) or not _IDENTIFIER.fullmatch(key) or not _text(value)
               for key, value in checks.items()):
            raise ValueError(f"{identifier}: checks need valid IDs and nonempty descriptions")
    return scenarios


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PACK)
    parser.add_argument("--allow-holdout", action="store_true",
                        help="explicitly permit offline validation of a holdout pack")
    args = parser.parse_args()
    try:
        scenarios = load_pack(args.path, allow_holdout=args.allow_holdout)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"validated_scenario_ids": [s["id"] for s in scenarios],
                      "model_calls": 0, "generation_performed": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
