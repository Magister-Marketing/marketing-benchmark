"""Backend-neutral, versioned UI validation extension points."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from typing import Any, Protocol, Sequence


class UiValidator(Protocol):
    """Validate one backend-native UI specification."""

    def __call__(self, spec: Any) -> Sequence[str]:
        """Return an empty sequence when valid, otherwise explain each error."""


@dataclass(frozen=True)
class UiValidationResult:
    validator_id: str
    validator_version: str
    contract_id: str
    passed: bool
    findings: tuple[str, ...] = ()
    evidence: tuple[dict[str, Any], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class UiValidatorPlugin(Protocol):
    id: str
    version: str

    def validate(self, contract_id: str, spec: Any) -> UiValidationResult:
        """Validate one spec against one declared versioned contract."""


class UiValidatorRegistry:
    def __init__(self) -> None:
        self._validators: dict[str, UiValidatorPlugin] = {}

    def register(self, contract_id: str, validator: UiValidatorPlugin) -> None:
        if contract_id in self._validators:
            raise ValueError(f"duplicate UI contract: {contract_id}")
        self._validators[contract_id] = validator

    def validator_for(
        self,
        contracts: tuple[str, ...],
        *,
        results: list[UiValidationResult] | None = None,
    ) -> UiValidator:
        def validate(spec: Any) -> list[str]:
            errors: list[str] = []
            for contract_id in contracts:
                validator = self._validators.get(contract_id)
                if validator is None:
                    result = UiValidationResult(
                        validator_id="missing",
                        validator_version="0",
                        contract_id=contract_id,
                        passed=False,
                        findings=(f"no validator registered for {contract_id}",),
                    )
                else:
                    result = validator.validate(contract_id, spec)
                if results is not None:
                    results.append(result)
                errors.extend(
                    f"{contract_id}: {finding}" for finding in result.findings
                )
            return errors

        return validate


class CallableUiValidator:
    def __init__(self, validator_id: str, version: str, callback: UiValidator) -> None:
        self.id = validator_id
        self.version = version
        self.callback = callback

    def validate(self, contract_id: str, spec: Any) -> UiValidationResult:
        findings = tuple(str(value) for value in self.callback(spec))
        return UiValidationResult(
            validator_id=self.id,
            validator_version=self.version,
            contract_id=contract_id,
            passed=not findings,
            findings=findings,
        )


class JsonObjectValidator:
    """Dependency-free public baseline for structured JSON response contracts."""

    id = "json-object"
    version = "1"

    def __init__(self, *, required_keys: tuple[str, ...] = ()) -> None:
        self.required_keys = required_keys

    def validate(self, contract_id: str, spec: Any) -> UiValidationResult:
        findings: list[str] = []
        if not isinstance(spec, dict):
            findings.append("value must be a JSON object")
        else:
            missing = sorted(set(self.required_keys) - set(spec))
            if missing:
                findings.append("missing required keys: " + ", ".join(missing))
        return UiValidationResult(
            validator_id=self.id,
            validator_version=self.version,
            contract_id=contract_id,
            passed=not findings,
            findings=tuple(findings),
        )


class JsonSchemaValidator:
    """Validate structured UI data with the optional standards-compliant library."""

    id = "json-schema"
    version = "1"

    def __init__(self, schema: dict[str, Any]) -> None:
        self.schema = dict(schema)

    def validate(self, contract_id: str, spec: Any) -> UiValidationResult:
        findings: list[str] = []
        try:
            from jsonschema import Draft202012Validator

            Draft202012Validator.check_schema(self.schema)
            validator = Draft202012Validator(self.schema)
            findings.extend(
                f"{list(error.path)}: {error.message}"
                for error in sorted(
                    validator.iter_errors(spec), key=lambda value: list(value.path)
                )
            )
        except ImportError:
            findings.append(
                "jsonschema is not installed; install the ui validation extra"
            )
        except Exception as exc:
            findings.append(f"JSON Schema validation failed: {exc}")
        return UiValidationResult(
            validator_id=self.id,
            validator_version=self.version,
            contract_id=contract_id,
            passed=not findings,
            findings=tuple(findings),
            evidence=(
                {
                    "schema_sha256": hashlib.sha256(
                        json.dumps(self.schema, sort_keys=True).encode()
                    ).hexdigest()
                },
            ),
        )


class _HtmlStructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)


class StaticHtmlValidator:
    """Portable structural gate used before optional Playwright render judging."""

    id = "static-html"
    version = "1"

    def validate(self, contract_id: str, spec: Any) -> UiValidationResult:
        findings: list[str] = []
        if not isinstance(spec, str) or not spec.strip():
            findings.append("HTML must be a non-empty string")
        else:
            parser = _HtmlStructureParser()
            try:
                parser.feed(spec)
            except Exception as exc:
                findings.append(f"HTML parse failed: {exc}")
            if "main" not in parser.tags:
                findings.append("HTML needs a main landmark")
            if not any(tag in parser.tags for tag in ("h1", "h2")):
                findings.append("HTML needs a visible heading")
        return UiValidationResult(
            validator_id=self.id,
            validator_version=self.version,
            contract_id=contract_id,
            passed=not findings,
            findings=tuple(findings),
        )


class PlaywrightHtmlValidator:
    """Opt-in offline desktop/mobile render validator with screenshot hashes."""

    id = "playwright-html"
    version = "1"

    def __init__(
        self,
        *,
        viewports: tuple[tuple[str, int, int], ...] = (
            ("desktop", 1440, 900),
            ("mobile", 390, 844),
        ),
    ) -> None:
        self.viewports = viewports

    def validate(self, contract_id: str, spec: Any) -> UiValidationResult:
        structural = StaticHtmlValidator().validate(contract_id, spec)
        findings = list(structural.findings)
        evidence: list[dict[str, Any]] = []
        if findings:
            return UiValidationResult(
                validator_id=self.id,
                validator_version=self.version,
                contract_id=contract_id,
                passed=False,
                findings=tuple(findings),
            )
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            findings.append(
                "playwright is not installed; install the ui validation extra and Chromium"
            )
            return UiValidationResult(
                validator_id=self.id,
                validator_version=self.version,
                contract_id=contract_id,
                passed=False,
                findings=tuple(findings),
            )
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    for label, width, height in self.viewports:
                        page = browser.new_page(
                            viewport={"width": width, "height": height}
                        )
                        console_errors: list[str] = []
                        page.on(
                            "console",
                            lambda message: (
                                console_errors.append(message.text)
                                if message.type == "error"
                                else None
                            ),
                        )
                        page.route("**/*", lambda route: route.abort())
                        page.set_content(str(spec), wait_until="domcontentloaded")
                        checks = page.evaluate(
                            """() => ({
                              main: Boolean(document.querySelector('main')),
                              heading: Boolean(document.querySelector('h1,h2')),
                              overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
                              unlabeledControls: Array.from(document.querySelectorAll('button,[role="button"],input,select,textarea')).filter((node) => {
                                const label = node.getAttribute('aria-label') || node.getAttribute('title') || node.textContent || node.getAttribute('placeholder') || '';
                                return !String(label).trim();
                              }).length
                            })"""
                        )
                        if checks.get("overflow"):
                            findings.append(f"{label}: horizontal overflow")
                        if checks.get("unlabeledControls"):
                            findings.append(
                                f"{label}: {checks['unlabeledControls']} unlabeled control(s)"
                            )
                        findings.extend(
                            f"{label}: console error: {value}"
                            for value in console_errors[:10]
                        )
                        screenshot = page.screenshot(full_page=True)
                        evidence.append(
                            {
                                "viewport": label,
                                "width": width,
                                "height": height,
                                "screenshot_sha256": hashlib.sha256(
                                    screenshot
                                ).hexdigest(),
                                "screenshot_bytes": len(screenshot),
                            }
                        )
                        page.close()
                finally:
                    browser.close()
        except Exception as exc:
            findings.append(f"Playwright render failed: {exc}")
        return UiValidationResult(
            validator_id=self.id,
            validator_version=self.version,
            contract_id=contract_id,
            passed=not findings,
            findings=tuple(findings),
            evidence=tuple(evidence),
        )
