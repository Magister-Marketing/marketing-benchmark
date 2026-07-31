"""Strict, versioned manifest loading for agent evaluations."""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = 1
MANIFEST_SCHEMA_VERSIONS = frozenset({1, 2})
EFFORT_LEVELS = frozenset({"low", "medium", "high", "xhigh", "max"})
VERBOSITY_LEVELS = frozenset({"low", "medium", "high"})
KNOWN_CAPABILITIES = frozenset(
    {
        "analytics.read",
        "search.read",
        "ads.read",
        "ads.draft",
        "ads.activate",
        "crm.read",
        "crm.write",
        "commerce.read",
        "commerce.write",
        "content.draft",
        "content.publish",
        "email.draft",
        "email.send",
        "social.draft",
        "social.publish",
        "files.read",
        "files.write",
        "browser.read",
        "browser.act",
    }
)
SIDE_EFFECT_CLASSES = frozenset(
    {
        "none",
        "internal_write",
        "draft",
        "external_write",
        "send",
        "publish",
        "spend",
        "delete",
    }
)
ENVIRONMENT_MODES = frozenset({"none", "replay", "live"})
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,95}$")
_PROGRAMMATIC_KINDS = frozenset(
    {
        "minimum_heading_matches",
        "labeled_character_limit",
        "numbered_section_count",
        "required_label_per_section",
        "required_heading_level",
        "required_label",
        "required_phrase",
        "required_headings",
    }
)


class ManifestError(ValueError):
    """A manifest is invalid or references an unsafe/missing resource."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise ManifestError(f"manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ManifestError(f"manifest must be a JSON object: {path}")
    return value


def _reject_unknown(data: dict[str, Any], allowed: set[str], path: Path) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ManifestError(f"unknown field(s) in {path}: {', '.join(unknown)}")


def _require_fields(data: dict[str, Any], required: set[str], path: Path) -> None:
    missing = sorted(required - set(data))
    if missing:
        raise ManifestError(f"missing required field(s) in {path}: {', '.join(missing)}")


def _require_version(
    data: dict[str, Any],
    path: Path,
    *,
    allowed: frozenset[int] = frozenset({SCHEMA_VERSION}),
) -> int:
    version = data.get("schema_version")
    if version not in allowed:
        raise ManifestError(
            f"{path} must use schema_version in {sorted(allowed)}; got {version!r}"
        )
    return int(version)


def _require_id(value: Any, field_name: str, path: Path) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise ManifestError(
            f"{field_name} in {path} must match {_ID_RE.pattern!r}"
        )
    return value


def _require_string(value: Any, field_name: str, path: Path) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{field_name} in {path} must be a non-empty string")
    return value.strip()


def _string_list(value: Any, field_name: str, path: Path) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ManifestError(f"{field_name} in {path} must be an array of strings")
    normalized = tuple(item.strip() for item in value)
    if len(set(normalized)) != len(normalized):
        raise ManifestError(f"{field_name} in {path} contains duplicates")
    return normalized


def _positive_int(value: Any, field_name: str, path: Path) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ManifestError(f"{field_name} in {path} must be a positive integer")
    return value


def _positive_number(value: Any, field_name: str, path: Path) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ManifestError(f"{field_name} in {path} must be a positive number")
    return float(value)


def _safe_repo_path(value: Any, field_name: str, path: Path) -> str:
    text = _require_string(value, field_name, path)
    candidate = PurePosixPath(text)
    if candidate.is_absolute() or ".." in candidate.parts or "\\" in text:
        raise ManifestError(f"{field_name} in {path} must be a safe repo-relative path")
    return candidate.as_posix()


def canonical_hash(value: Any) -> str:
    """Return a stable SHA-256 for a JSON-serializable manifest value."""
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def content_hash(path: Path) -> str:
    """Hash a regular file or directory tree with stable relative paths."""
    if path.is_file() and not path.is_symlink():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    if not path.is_dir() or path.is_symlink():
        raise ManifestError(f"cannot hash missing or symlinked content: {path}")
    digest = hashlib.sha256()
    files = sorted(item for item in path.rglob("*") if item.is_file())
    if not files:
        raise ManifestError(f"content directory is empty: {path}")
    for item in files:
        if item.is_symlink():
            raise ManifestError(f"content directory contains a symlink: {item}")
        relative = item.relative_to(path).as_posix().encode()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        payload = item.read_bytes()
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _validate_fixture(fixture_path: Path, manifest_path: Path) -> None:
    context = fixture_path / "product-marketing.md"
    constraints_path = fixture_path / "constraints.json"
    if not context.is_file() or context.is_symlink():
        raise ManifestError(f"fixture needs product-marketing.md for {manifest_path}")
    constraints = _read_json(constraints_path)
    allowed = {
        "fixture_version",
        "authoritative_sources",
        "forbidden_claims",
        "required_copy",
        "allowed_side_effects",
        "required_disclosure",
    }
    _reject_unknown(constraints, allowed, constraints_path)
    if constraints.get("fixture_version") != 1:
        raise ManifestError(f"fixture_version must be 1 in {constraints_path}")
    sources = _string_list(
        constraints.get("authoritative_sources"),
        "authoritative_sources",
        constraints_path,
    )
    if not sources:
        raise ManifestError(f"authoritative_sources cannot be empty in {constraints_path}")
    for source in sources:
        safe_source = _safe_repo_path(source, "authoritative_sources", constraints_path)
        source_path = (fixture_path / safe_source).resolve()
        try:
            source_path.relative_to(fixture_path.resolve())
        except ValueError as exc:
            raise ManifestError(
                f"authoritative source escapes fixture: {source}"
            ) from exc
        if not source_path.is_file() or source_path.is_symlink():
            raise ManifestError(f"authoritative source is missing: {source_path}")
    for field_name in ("forbidden_claims", "required_copy", "allowed_side_effects"):
        _string_list(constraints.get(field_name), field_name, constraints_path)
    _require_string(
        constraints.get("required_disclosure"),
        "required_disclosure",
        constraints_path,
    )


def _validate_rubric_extensions(data: dict[str, Any], path: Path) -> None:
    """Validate the optional shared-schema fields from issue #900.

    These carry judge pinning, verdict collapse, and human-calibration
    provenance so one rubric runs in both this runner and the open
    marketing-skills framework. All of them are optional; hard gates and
    programmatic checks stay deterministic in every engine.
    """
    prompt = data.get("prompt")
    if prompt is not None:
        if not isinstance(prompt, dict):
            raise ManifestError(f"prompt in {path} must be an object")
        _reject_unknown(prompt, {"render"}, path)
        _require_string(prompt.get("render"), "prompt.render", path)
    verdict_policy = data.get("verdict_policy")
    if verdict_policy is not None:
        if not isinstance(verdict_policy, dict):
            raise ManifestError(f"verdict_policy in {path} must be an object")
        _reject_unknown(verdict_policy, {"pass_if", "score"}, path)
        _require_string(verdict_policy.get("pass_if"), "verdict_policy.pass_if", path)
        _require_string(verdict_policy.get("score"), "verdict_policy.score", path)
    judge = data.get("judge")
    if judge is not None:
        if not isinstance(judge, dict):
            raise ManifestError(f"judge in {path} must be an object")
        _reject_unknown(judge, {"model", "temperature", "rubric_version"}, path)
        _require_string(judge.get("model"), "judge.model", path)
        _require_string(judge.get("rubric_version"), "judge.rubric_version", path)
        if judge.get("temperature") != 0:
            raise ManifestError(
                f"judge.temperature in {path} must be pinned to 0 for reproducibility"
            )
    calibration = data.get("calibration")
    if calibration is not None:
        if not isinstance(calibration, dict):
            raise ManifestError(f"calibration in {path} must be an object")
        _reject_unknown(
            calibration, {"answer_key", "labeler", "agreement", "method"}, path
        )
        answer_key = calibration.get("answer_key")
        if answer_key is not None:
            _require_string(answer_key, "calibration.answer_key", path)
        for field_name in ("labeler", "method"):
            if calibration.get(field_name) is not None:
                _require_string(
                    calibration.get(field_name), f"calibration.{field_name}", path
                )
        agreement = calibration.get("agreement")
        if agreement is not None and (
            isinstance(agreement, bool)
            or not isinstance(agreement, (int, float))
            or not 0 <= agreement <= 100
        ):
            raise ManifestError(
                f"calibration.agreement in {path} must be null or between 0 and 100"
            )
    if data.get("provenance") is not None:
        _require_string(data.get("provenance"), "provenance", path)


def _validate_rubric(path: Path, task_family: str) -> None:
    data = _read_json(path)
    _reject_unknown(
        data,
        {
            "schema_version",
            "id",
            "task_family",
            "hard_gates",
            "programmatic_checks",
            "subjective_dimensions",
            "prompt",
            "verdict_policy",
            "judge",
            "calibration",
            "provenance",
        },
        path,
    )
    _validate_rubric_extensions(data, path)
    _require_version(data, path)
    _require_id(data.get("id"), "id", path)
    if data.get("task_family") != task_family:
        raise ManifestError(
            f"rubric task_family in {path} does not match scenario {task_family!r}"
        )
    hard_gates = data.get("hard_gates")
    dimensions = data.get("subjective_dimensions")
    checks = data.get("programmatic_checks", [])
    if not isinstance(hard_gates, list) or not hard_gates:
        raise ManifestError(f"hard_gates in {path} must be a non-empty array")
    if not isinstance(dimensions, list) or not dimensions:
        raise ManifestError(
            f"subjective_dimensions in {path} must be a non-empty array"
        )
    if not isinstance(checks, list):
        raise ManifestError(f"programmatic_checks in {path} must be an array")
    seen: set[str] = set()
    for row in hard_gates:
        if not isinstance(row, dict) or set(row) != {"id", "description"}:
            raise ManifestError(
                f"each hard gate in {path} needs only id and description"
            )
        row_id = _require_id(row.get("id"), "hard_gates.id", path)
        _require_string(row.get("description"), "hard_gates.description", path)
        if row_id in seen:
            raise ManifestError(f"duplicate rubric id in {path}: {row_id}")
        seen.add(row_id)
    for row in dimensions:
        if not isinstance(row, dict) or not (
            {"id", "scale", "description"}
            <= set(row)
            <= {"id", "scale", "description", "anchors"}
        ):
            raise ManifestError(
                f"each subjective dimension in {path} needs id, scale, description "
                "and at most optional anchors"
            )
        row_id = _require_id(row.get("id"), "subjective_dimensions.id", path)
        scale = row.get("scale")
        if (
            not isinstance(scale, list)
            or len(scale) != 2
            or any(isinstance(value, bool) or not isinstance(value, int) for value in scale)
            or scale[0] >= scale[1]
        ):
            raise ManifestError(f"invalid subjective scale in {path}: {scale!r}")
        _require_string(
            row.get("description"), "subjective_dimensions.description", path
        )
        anchors = row.get("anchors")
        if anchors is not None:
            if not isinstance(anchors, dict) or not anchors:
                raise ManifestError(
                    f"anchors for {row_id} in {path} must be a non-empty object"
                )
            for key, value in anchors.items():
                try:
                    anchor_point = int(key)
                except (TypeError, ValueError) as exc:
                    raise ManifestError(
                        f"anchor key {key!r} for {row_id} in {path} must be an integer"
                    ) from exc
                if not scale[0] <= anchor_point <= scale[1]:
                    raise ManifestError(
                        f"anchor {key} for {row_id} in {path} is outside the scale"
                    )
                _require_string(value, f"anchors.{key}", path)
        if row_id in seen:
            raise ManifestError(f"duplicate rubric id in {path}: {row_id}")
        seen.add(row_id)
    allowed_check_fields = {
        "id",
        "kind",
        "pattern",
        "minimum",
        "maximum",
        "label",
        "prefix",
        "level",
        "count",
        "phrase",
        "values",
    }
    for row in checks:
        if not isinstance(row, dict):
            raise ManifestError(f"programmatic check in {path} must be an object")
        unknown = sorted(set(row) - allowed_check_fields)
        if unknown:
            raise ManifestError(
                f"unknown programmatic check fields in {path}: {', '.join(unknown)}"
            )
        row_id = _require_id(row.get("id"), "programmatic_checks.id", path)
        if row_id in seen:
            raise ManifestError(f"duplicate rubric id in {path}: {row_id}")
        seen.add(row_id)
        if row.get("kind") not in _PROGRAMMATIC_KINDS:
            raise ManifestError(
                f"unsupported programmatic check kind in {path}: {row.get('kind')!r}"
            )


@dataclass(frozen=True)
class SettingRequest:
    mode: str
    value: Any = None

    def as_dict(self) -> dict[str, Any]:
        result = {"mode": self.mode}
        if self.mode == "set":
            result["value"] = self.value
        return result


def _setting_request(
    value: Any,
    *,
    name: str,
    path: Path,
) -> SettingRequest:
    if not isinstance(value, dict):
        raise ManifestError(f"settings.{name} in {path} must be an object")
    _reject_unknown(value, {"mode", "value"}, path)
    mode = value.get("mode")
    if mode not in {"set", "omit", "provider_default"}:
        raise ManifestError(
            f"settings.{name}.mode in {path} must be set, omit, or provider_default"
        )
    if mode == "set" and "value" not in value:
        raise ManifestError(f"settings.{name} in {path} needs a value when mode=set")
    if mode != "set" and "value" in value:
        raise ManifestError(
            f"settings.{name} in {path} cannot contain value when mode={mode}"
        )
    setting_value = value.get("value")
    if name == "reasoning_effort" and mode == "set" and setting_value not in EFFORT_LEVELS:
        raise ManifestError(f"unsupported reasoning effort in {path}: {setting_value!r}")
    if name == "text_verbosity" and mode == "set" and setting_value not in VERBOSITY_LEVELS:
        raise ManifestError(f"unsupported text verbosity in {path}: {setting_value!r}")
    if name == "temperature" and mode == "set" and (
        isinstance(setting_value, bool)
        or not isinstance(setting_value, (int, float))
        or not math.isfinite(float(setting_value))
    ):
        raise ManifestError(f"temperature in {path} must be a finite number")
    if name == "max_output_tokens" and mode == "set":
        _positive_int(setting_value, "settings.max_output_tokens.value", path)
        if setting_value > 128_000:
            raise ManifestError(f"max_output_tokens in {path} cannot exceed 128000")
    return SettingRequest(mode=mode, value=setting_value)


@dataclass(frozen=True)
class Candidate:
    id: str
    model: str
    effort: str | None
    verbosity: str | None
    temperature_policy: str
    max_output_tokens: int
    cost_ceiling_usd_per_attempt: float
    source_path: Path = field(repr=False)
    manifest_hash: str
    schema_version: int = 1
    agent_adapter: str | None = None
    setting_requests: dict[str, SettingRequest] = field(default_factory=dict)
    unsupported_setting_policy: str = "error"

    def requested_settings(self) -> dict[str, dict[str, Any]]:
        if self.setting_requests:
            return {
                name: request.as_dict()
                for name, request in sorted(self.setting_requests.items())
            }
        return {
            "reasoning_effort": {
                "mode": "set" if self.effort is not None else "omit",
                **({"value": self.effort} if self.effort is not None else {}),
            },
            "text_verbosity": {
                "mode": "set" if self.verbosity is not None else "omit",
                **({"value": self.verbosity} if self.verbosity is not None else {}),
            },
            "temperature": {"mode": self.temperature_policy},
            "max_output_tokens": {"mode": "set", "value": self.max_output_tokens},
        }

    @classmethod
    def load(cls, path: Path) -> "Candidate":
        data = _read_json(path)
        version = _require_version(data, path, allowed=MANIFEST_SCHEMA_VERSIONS)
        if version == 2:
            _require_fields(
                data,
                {
                    "id",
                    "agent_adapter",
                    "model",
                    "settings",
                    "unsupported_setting_policy",
                    "cost_ceiling_usd_per_attempt",
                },
                path,
            )
            _reject_unknown(
                data,
                {
                    "schema_version",
                    "id",
                    "agent_adapter",
                    "model",
                    "settings",
                    "unsupported_setting_policy",
                    "cost_ceiling_usd_per_attempt",
                    "description",
                },
                path,
            )
            settings = data.get("settings")
            if not isinstance(settings, dict):
                raise ManifestError(f"settings in {path} must be an object")
            allowed_settings = {
                "reasoning_effort",
                "text_verbosity",
                "temperature",
                "max_output_tokens",
            }
            _reject_unknown(settings, allowed_settings, path)
            missing = sorted(allowed_settings - set(settings))
            if missing:
                raise ManifestError(
                    f"settings in {path} must declare every portable setting: "
                    + ", ".join(missing)
                )
            requests = {
                name: _setting_request(settings[name], name=name, path=path)
                for name in sorted(settings)
            }
            max_tokens = requests["max_output_tokens"]
            if max_tokens.mode != "set":
                raise ManifestError(
                    f"settings.max_output_tokens in {path} must use mode=set"
                )
            policy = data.get("unsupported_setting_policy", "error")
            if policy != "error":
                raise ManifestError(
                    f"unsupported_setting_policy in {path} must be 'error'"
                )
            return cls(
                id=_require_id(data.get("id"), "id", path),
                model=_require_string(data.get("model"), "model", path),
                effort=(
                    requests["reasoning_effort"].value
                    if requests["reasoning_effort"].mode == "set"
                    else None
                ),
                verbosity=(
                    requests["text_verbosity"].value
                    if requests["text_verbosity"].mode == "set"
                    else None
                ),
                temperature_policy=requests["temperature"].mode,
                max_output_tokens=int(max_tokens.value),
                cost_ceiling_usd_per_attempt=_positive_number(
                    data.get("cost_ceiling_usd_per_attempt"),
                    "cost_ceiling_usd_per_attempt",
                    path,
                ),
                source_path=path.resolve(),
                manifest_hash=canonical_hash(data),
                schema_version=2,
                agent_adapter=_require_id(
                    data.get("agent_adapter"), "agent_adapter", path
                ),
                setting_requests=requests,
                unsupported_setting_policy=policy,
            )
        _reject_unknown(
            data,
            {
                "schema_version",
                "id",
                "model",
                "effort",
                "verbosity",
                "temperature_policy",
                "max_output_tokens",
                "cost_ceiling_usd_per_attempt",
                "description",
            },
            path,
        )
        for required_field in ("effort", "verbosity"):
            if required_field not in data:
                raise ManifestError(f"{required_field} must be explicit in {path}")
        candidate_id = _require_id(data.get("id"), "id", path)
        model = _require_string(data.get("model"), "model", path)
        effort = data.get("effort")
        if effort is not None and effort not in EFFORT_LEVELS:
            raise ManifestError(f"unsupported effort in {path}: {effort!r}")
        verbosity = data.get("verbosity")
        if verbosity is not None and verbosity not in VERBOSITY_LEVELS:
            raise ManifestError(f"unsupported verbosity in {path}: {verbosity!r}")
        if model.startswith("anthropic/") and verbosity is not None:
            raise ManifestError(f"Anthropic candidate {candidate_id} cannot set verbosity")
        if model.startswith("openai/gpt-5") and verbosity is None:
            raise ManifestError(
                f"OpenAI GPT-5 candidate {candidate_id} must declare applied verbosity"
            )
        temperature_policy = data.get("temperature_policy")
        if temperature_policy != "omit":
            raise ManifestError(
                f"temperature_policy in {path} must be 'omit'; temperature is not a v1 knob"
            )
        max_output_tokens = _positive_int(
            data.get("max_output_tokens"), "max_output_tokens", path
        )
        if max_output_tokens > 128_000:
            raise ManifestError(f"max_output_tokens in {path} cannot exceed 128000")
        return cls(
            id=candidate_id,
            model=model,
            effort=effort,
            verbosity=verbosity,
            temperature_policy=temperature_policy,
            max_output_tokens=max_output_tokens,
            cost_ceiling_usd_per_attempt=_positive_number(
                data.get("cost_ceiling_usd_per_attempt"),
                "cost_ceiling_usd_per_attempt",
                path,
            ),
            source_path=path.resolve(),
            manifest_hash=canonical_hash(data),
            schema_version=1,
        )


@dataclass(frozen=True)
class ArtifactContract:
    required: bool = False
    relative_path: str | None = None
    media_type: str | None = None
    min_bytes: int = 1
    id: str = "primary"

    @classmethod
    def load(cls, value: Any, path: Path) -> "ArtifactContract":
        if value is None:
            return cls()
        if not isinstance(value, dict):
            raise ManifestError(f"artifact in {path} must be an object")
        _reject_unknown(
            value,
            {"id", "required", "relative_path", "media_type", "min_bytes"},
            path,
        )
        required = value.get("required", False)
        if not isinstance(required, bool):
            raise ManifestError(f"artifact.required in {path} must be a boolean")
        relative_path = value.get("relative_path")
        if relative_path is not None:
            relative_path = _safe_repo_path(relative_path, "artifact.relative_path", path)
        if required and not relative_path:
            raise ManifestError(f"required artifact in {path} needs relative_path")
        media_type = value.get("media_type")
        if media_type is not None:
            media_type = _require_string(media_type, "artifact.media_type", path)
        min_bytes = value.get("min_bytes", 1)
        return cls(
            required=required,
            relative_path=relative_path,
            media_type=media_type,
            min_bytes=_positive_int(min_bytes, "artifact.min_bytes", path),
            id=(
                _require_id(value.get("id"), "artifact.id", path)
                if value.get("id") is not None
                else "primary"
            ),
        )


@dataclass(frozen=True)
class Scenario:
    id: str
    suite: str
    task_family: str
    version: int
    prompt: str
    fixture_dir: str
    required_skill_reads: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    forbidden_side_effects: tuple[str, ...]
    require_ui_spec: bool
    artifact: ArtifactContract
    rubric: str | None
    timeout_seconds: int
    max_model_calls: int
    tags: tuple[str, ...]
    source_path: Path = field(repr=False)
    manifest_hash: str
    prompt_hash: str
    fixture_hash: str
    rubric_hash: str
    schema_version: int = 1
    fixture_dirs: tuple[str, ...] = ()
    environment_plugin: str | None = None
    environment_fixture: str | None = None
    environment_mode: str = "none"
    fixed_clock: str | None = None
    capabilities: tuple[str, ...] = ()
    allowed_operations: tuple[str, ...] = ()
    artifacts: tuple[ArtifactContract, ...] = ()
    ui_contracts: tuple[str, ...] = ()
    scorers: tuple[str, ...] = ()

    @classmethod
    def load(cls, path: Path, repo_root: Path) -> "Scenario":
        data = _read_json(path)
        version = _require_version(data, path, allowed=MANIFEST_SCHEMA_VERSIONS)
        if version == 2:
            return cls._load_v2(data, path, repo_root)
        _reject_unknown(
            data,
            {
                "schema_version",
                "id",
                "suite",
                "task_family",
                "version",
                "prompt",
                "fixture_dir",
                "required_skill_reads",
                "allowed_tools",
                "forbidden_side_effects",
                "require_ui_spec",
                "artifact",
                "rubric",
                "timeout_seconds",
                "max_model_calls",
                "tags",
                "description",
            },
            path,
        )
        fixture_dir = _safe_repo_path(data.get("fixture_dir"), "fixture_dir", path)
        fixture_path = (repo_root / fixture_dir).resolve()
        try:
            fixture_path.relative_to(repo_root.resolve())
        except ValueError as exc:
            raise ManifestError(f"fixture_dir escapes repository in {path}") from exc
        if not fixture_path.is_dir():
            raise ManifestError(f"fixture_dir does not exist for {path}: {fixture_dir}")
        _validate_fixture(fixture_path, path)
        rubric = _safe_repo_path(data.get("rubric"), "rubric", path)
        rubric_path = (repo_root / rubric).resolve()
        try:
            rubric_path.relative_to(repo_root.resolve())
        except ValueError as exc:
            raise ManifestError(f"rubric escapes repository in {path}") from exc
        if not rubric_path.is_file():
            raise ManifestError(f"rubric does not exist for {path}: {rubric}")
        task_family = _require_id(data.get("task_family"), "task_family", path)
        _validate_rubric(rubric_path, task_family)
        require_ui_spec = data.get("require_ui_spec", False)
        if not isinstance(require_ui_spec, bool):
            raise ManifestError(f"require_ui_spec in {path} must be a boolean")
        return cls(
            id=_require_id(data.get("id"), "id", path),
            suite=_require_id(data.get("suite"), "suite", path),
            task_family=task_family,
            version=_positive_int(data.get("version"), "version", path),
            prompt=_require_string(data.get("prompt"), "prompt", path),
            fixture_dir=fixture_dir,
            required_skill_reads=_string_list(
                data.get("required_skill_reads"), "required_skill_reads", path
            ),
            allowed_tools=_string_list(data.get("allowed_tools"), "allowed_tools", path),
            forbidden_side_effects=_string_list(
                data.get("forbidden_side_effects"), "forbidden_side_effects", path
            ),
            require_ui_spec=require_ui_spec,
            artifact=ArtifactContract.load(data.get("artifact"), path),
            rubric=rubric,
            timeout_seconds=_positive_int(
                data.get("timeout_seconds"), "timeout_seconds", path
            ),
            max_model_calls=_positive_int(
                data.get("max_model_calls"), "max_model_calls", path
            ),
            tags=_string_list(data.get("tags"), "tags", path),
            source_path=path.resolve(),
            manifest_hash=canonical_hash(data),
            prompt_hash=canonical_hash(data.get("prompt")),
            fixture_hash=content_hash(fixture_path),
            rubric_hash=content_hash(rubric_path),
            schema_version=1,
            fixture_dirs=(fixture_dir,),
            artifacts=(ArtifactContract.load(data.get("artifact"), path),),
            ui_contracts=("magister-json-render@1",) if require_ui_spec else (),
        )

    @classmethod
    def _load_v2(
        cls,
        data: dict[str, Any],
        path: Path,
        repo_root: Path,
    ) -> "Scenario":
        _require_fields(
            data,
            {
                "id",
                "suite",
                "task_family",
                "version",
                "prompt",
                "fixtures",
                "environment",
                "capabilities",
                "tool_policy",
                "requirements",
                "scorers",
                "timeout_seconds",
                "max_model_calls",
                "tags",
            },
            path,
        )
        _reject_unknown(
            data,
            {
                "schema_version",
                "id",
                "suite",
                "task_family",
                "version",
                "description",
                "prompt",
                "fixtures",
                "environment",
                "capabilities",
                "tool_policy",
                "requirements",
                "scorers",
                "rubric",
                "timeout_seconds",
                "max_model_calls",
                "tags",
            },
            path,
        )
        fixture_dirs = _string_list(data.get("fixtures"), "fixtures", path)
        fixture_hashes: list[dict[str, str]] = []
        for fixture_dir in fixture_dirs:
            safe_fixture = _safe_repo_path(fixture_dir, "fixtures", path)
            fixture_path = (repo_root / safe_fixture).resolve()
            try:
                fixture_path.relative_to(repo_root.resolve())
            except ValueError as exc:
                raise ManifestError(f"fixture escapes repository in {path}") from exc
            if not fixture_path.exists() or fixture_path.is_symlink():
                raise ManifestError(f"fixture does not exist for {path}: {safe_fixture}")
            fixture_hashes.append(
                {"path": safe_fixture, "sha256": content_hash(fixture_path)}
            )

        environment = data.get("environment") or {
            "plugin": "none",
            "mode": "none",
        }
        if not isinstance(environment, dict):
            raise ManifestError(f"environment in {path} must be an object")
        _reject_unknown(environment, {"plugin", "fixture", "mode", "clock"}, path)
        environment_plugin = _require_id(
            environment.get("plugin"), "environment.plugin", path
        )
        environment_mode = _require_id(
            environment.get("mode"), "environment.mode", path
        )
        if environment_mode not in ENVIRONMENT_MODES:
            raise ManifestError(
                f"unknown environment mode in {path}: {environment_mode!r}"
            )
        if environment_plugin == "none" and environment_mode != "none":
            raise ManifestError(
                f"environment.plugin=none in {path} requires environment.mode=none"
            )
        if environment_plugin != "none" and environment_mode == "none":
            raise ManifestError(
                f"environment.plugin={environment_plugin} in {path} cannot use "
                "environment.mode=none"
            )
        environment_fixture = environment.get("fixture")
        if environment_fixture is not None:
            environment_fixture = _require_id(
                environment_fixture, "environment.fixture", path
            )
        fixed_clock = environment.get("clock")
        if fixed_clock is not None:
            fixed_clock = _require_string(fixed_clock, "environment.clock", path)

        tool_policy = data.get("tool_policy") or {}
        if not isinstance(tool_policy, dict):
            raise ManifestError(f"tool_policy in {path} must be an object")
        _reject_unknown(
            tool_policy,
            {"allowed_tools", "allowed_operations", "forbidden_side_effects"},
            path,
        )

        requirements = data.get("requirements") or {}
        if not isinstance(requirements, dict):
            raise ManifestError(f"requirements in {path} must be an object")
        _reject_unknown(
            requirements,
            {"skill_reads", "artifacts", "ui_contracts"},
            path,
        )
        raw_artifacts = requirements.get("artifacts") or []
        if not isinstance(raw_artifacts, list):
            raise ManifestError(f"requirements.artifacts in {path} must be an array")
        artifacts = tuple(ArtifactContract.load(value, path) for value in raw_artifacts)
        artifact = next((value for value in artifacts if value.required), None)
        if artifact is None:
            artifact = artifacts[0] if artifacts else ArtifactContract()

        task_family = _require_id(data.get("task_family"), "task_family", path)
        rubric = data.get("rubric")
        rubric_hash = canonical_hash(None)
        if rubric is not None:
            rubric = _safe_repo_path(rubric, "rubric", path)
            rubric_path = (repo_root / rubric).resolve()
            try:
                rubric_path.relative_to(repo_root.resolve())
            except ValueError as exc:
                raise ManifestError(f"rubric escapes repository in {path}") from exc
            if not rubric_path.is_file():
                raise ManifestError(f"rubric does not exist for {path}: {rubric}")
            _validate_rubric(rubric_path, task_family)
            rubric_hash = content_hash(rubric_path)

        ui_contracts = _string_list(
            requirements.get("ui_contracts"), "requirements.ui_contracts", path
        )
        capabilities = _string_list(data.get("capabilities"), "capabilities", path)
        unknown_capabilities = sorted(set(capabilities) - KNOWN_CAPABILITIES)
        if unknown_capabilities:
            raise ManifestError(
                f"unknown capabilities in {path}: {', '.join(unknown_capabilities)}"
            )
        forbidden_side_effects = _string_list(
            tool_policy.get("forbidden_side_effects"),
            "tool_policy.forbidden_side_effects",
            path,
        )
        unknown_side_effects = sorted(
            set(forbidden_side_effects) - SIDE_EFFECT_CLASSES
        )
        if unknown_side_effects:
            raise ManifestError(
                f"unknown side-effect classes in {path}: "
                + ", ".join(unknown_side_effects)
            )
        return cls(
            id=_require_id(data.get("id"), "id", path),
            suite=_require_id(data.get("suite"), "suite", path),
            task_family=task_family,
            version=_positive_int(data.get("version"), "version", path),
            prompt=_require_string(data.get("prompt"), "prompt", path),
            fixture_dir=fixture_dirs[0] if fixture_dirs else "",
            required_skill_reads=_string_list(
                requirements.get("skill_reads"), "requirements.skill_reads", path
            ),
            allowed_tools=_string_list(
                tool_policy.get("allowed_tools"), "tool_policy.allowed_tools", path
            ),
            forbidden_side_effects=forbidden_side_effects,
            require_ui_spec=bool(ui_contracts),
            artifact=artifact,
            rubric=rubric,
            timeout_seconds=_positive_int(
                data.get("timeout_seconds"), "timeout_seconds", path
            ),
            max_model_calls=_positive_int(
                data.get("max_model_calls"), "max_model_calls", path
            ),
            tags=_string_list(data.get("tags"), "tags", path),
            source_path=path.resolve(),
            manifest_hash=canonical_hash(data),
            prompt_hash=canonical_hash(data.get("prompt")),
            fixture_hash=canonical_hash(fixture_hashes),
            rubric_hash=rubric_hash,
            schema_version=2,
            fixture_dirs=fixture_dirs,
            environment_plugin=(
                None if environment_plugin == "none" else environment_plugin
            ),
            environment_fixture=environment_fixture,
            environment_mode=environment_mode,
            fixed_clock=fixed_clock,
            capabilities=capabilities,
            allowed_operations=_string_list(
                tool_policy.get("allowed_operations"),
                "tool_policy.allowed_operations",
                path,
            ),
            artifacts=artifacts,
            ui_contracts=ui_contracts,
            scorers=_string_list(data.get("scorers"), "scorers", path),
        )


@dataclass(frozen=True)
class ExperimentBudget:
    max_provider_cost_usd: float
    max_attempts: int
    deadline_seconds: int


@dataclass(frozen=True)
class Experiment:
    id: str
    candidates: tuple[str, ...]
    scenarios: tuple[str, ...]
    repetitions: int
    concurrency: int
    random_seed: int
    budget: ExperimentBudget
    judge: dict[str, Any]
    source_path: Path = field(repr=False)
    manifest_hash: str
    schema_version: int = 1
    comparison_mode: str = "model"

    @classmethod
    def load(cls, path: Path) -> "Experiment":
        data = _read_json(path)
        version = _require_version(data, path, allowed=MANIFEST_SCHEMA_VERSIONS)
        if version == 2:
            _require_fields(
                data,
                {
                    "id",
                    "comparison_mode",
                    "candidates",
                    "scenarios",
                    "repetitions",
                    "concurrency",
                    "random_seed",
                    "budget",
                    "judge",
                },
                path,
            )
        _reject_unknown(
            data,
            {
                "schema_version",
                "id",
                "candidates",
                "scenarios",
                "repetitions",
                "concurrency",
                "random_seed",
                "budget",
                "judge",
                "comparison_mode",
                "description",
            },
            path,
        )
        if version == 1 and "comparison_mode" in data:
            raise ManifestError(
                f"comparison_mode is a schema_version=2 field in {path}"
            )
        budget = data.get("budget")
        if not isinstance(budget, dict):
            raise ManifestError(f"budget in {path} must be an object")
        _reject_unknown(
            budget,
            {"max_provider_cost_usd", "max_attempts", "deadline_seconds"},
            path,
        )
        judge = data.get("judge", {"enabled": False})
        if not isinstance(judge, dict) or not isinstance(judge.get("enabled"), bool):
            raise ManifestError(f"judge in {path} must contain boolean enabled")
        _reject_unknown(judge, {"enabled"}, path)
        random_seed = data.get("random_seed")
        if isinstance(random_seed, bool) or not isinstance(random_seed, int):
            raise ManifestError(f"random_seed in {path} must be an integer")
        comparison_mode = data.get("comparison_mode", "model")
        if comparison_mode not in {"model", "agent_system"}:
            raise ManifestError(
                f"comparison_mode in {path} must be model or agent_system"
            )
        experiment = cls(
            id=_require_id(data.get("id"), "id", path),
            candidates=_string_list(data.get("candidates"), "candidates", path),
            scenarios=_string_list(data.get("scenarios"), "scenarios", path),
            repetitions=_positive_int(data.get("repetitions"), "repetitions", path),
            concurrency=_positive_int(data.get("concurrency"), "concurrency", path),
            random_seed=random_seed,
            budget=ExperimentBudget(
                max_provider_cost_usd=_positive_number(
                    budget.get("max_provider_cost_usd"),
                    "budget.max_provider_cost_usd",
                    path,
                ),
                max_attempts=_positive_int(
                    budget.get("max_attempts"), "budget.max_attempts", path
                ),
                deadline_seconds=_positive_int(
                    budget.get("deadline_seconds"), "budget.deadline_seconds", path
                ),
            ),
            judge=dict(judge),
            source_path=path.resolve(),
            manifest_hash=canonical_hash(data),
            schema_version=version,
            comparison_mode=comparison_mode,
        )
        if not experiment.candidates or not experiment.scenarios:
            raise ManifestError(f"{path} must select at least one candidate and scenario")
        return experiment


@dataclass(frozen=True)
class Trial:
    attempt_id: str
    scenario_id: str
    candidate_id: str
    repetition: int
    ordinal: int


@dataclass(frozen=True)
class Catalog:
    repo_root: Path
    candidates: dict[str, Candidate]
    scenarios: dict[str, Scenario]

    @classmethod
    def load(cls, repo_root: Path) -> "Catalog":
        root = repo_root.resolve()
        candidates: dict[str, Candidate] = {}
        for path in sorted((root / "evals" / "candidates").glob("*.json")):
            candidate = Candidate.load(path)
            if candidate.id in candidates:
                raise ManifestError(f"duplicate candidate id: {candidate.id}")
            candidates[candidate.id] = candidate

        scenarios: dict[str, Scenario] = {}
        for path in sorted((root / "evals" / "suites").glob("**/*.json")):
            scenario = Scenario.load(path, root)
            if scenario.id in scenarios:
                raise ManifestError(f"duplicate scenario id: {scenario.id}")
            scenarios[scenario.id] = scenario
        if not candidates:
            raise ManifestError("no candidate manifests found")
        if not scenarios:
            raise ManifestError("no scenario manifests found")
        return cls(repo_root=root, candidates=candidates, scenarios=scenarios)

    def resolve(self, experiment: Experiment) -> tuple[list[Candidate], list[Scenario]]:
        missing_candidates = sorted(set(experiment.candidates) - set(self.candidates))
        missing_scenarios = sorted(set(experiment.scenarios) - set(self.scenarios))
        if missing_candidates:
            raise ManifestError(
                f"experiment {experiment.id} references unknown candidates: "
                f"{', '.join(missing_candidates)}"
            )
        if missing_scenarios:
            raise ManifestError(
                f"experiment {experiment.id} references unknown scenarios: "
                f"{', '.join(missing_scenarios)}"
            )
        return (
            [self.candidates[item] for item in experiment.candidates],
            [self.scenarios[item] for item in experiment.scenarios],
        )


def build_trials(
    experiment: Experiment,
    candidates: list[Candidate],
    scenarios: list[Scenario],
) -> list[Trial]:
    """Create scenario-blocked, deterministically randomized trial order."""
    rng = random.Random(experiment.random_seed)
    trials: list[Trial] = []
    ordinal = 0
    for repetition in range(1, experiment.repetitions + 1):
        scenario_order = list(scenarios)
        rng.shuffle(scenario_order)
        for scenario in scenario_order:
            candidate_order = list(candidates)
            rng.shuffle(candidate_order)
            for candidate in candidate_order:
                ordinal += 1
                trials.append(
                    Trial(
                        attempt_id=(
                            f"{scenario.id}--{candidate.id}--r{repetition:02d}"
                        ),
                        scenario_id=scenario.id,
                        candidate_id=candidate.id,
                        repetition=repetition,
                        ordinal=ordinal,
                    )
                )
    if len(trials) > experiment.budget.max_attempts:
        raise ManifestError(
            f"experiment expands to {len(trials)} attempts but max_attempts is "
            f"{experiment.budget.max_attempts}"
        )
    return trials
