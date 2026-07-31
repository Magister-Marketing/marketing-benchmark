"""Minimal stdio MCP server for deterministic synthetic integration replay."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


class ReplayToolError(RuntimeError):
    def __init__(self, kind: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.kind = kind
        self.details = details


@dataclass
class ReplayGa4Service:
    fixture_dir: Path
    scenario_id: str

    def __post_init__(self) -> None:
        self.manifest = json.loads((self.fixture_dir / "manifest.json").read_text())
        self.tools = json.loads((self.fixture_dir / "tools.json").read_text())["tools"]
        self.dataset = json.loads((self.fixture_dir / "dataset.json").read_text())["rows"]
        scripts = self.manifest.get("scripts") or {}
        self.script = dict(scripts.get(self.scenario_id) or scripts.get("default") or {})
        self.calls: dict[str, int] = {}

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": tool["input_schema"],
            }
            for tool in self.tools
        ]

    def metadata_for(self, name: str) -> dict[str, str]:
        tool = next((tool for tool in self.tools if tool.get("name") == name), None)
        if tool is None:
            raise ReplayToolError("unknown_tool", f"Unknown replay tool: {name}")
        return {
            "operation": str(tool["operation"]),
            "integration": str(tool.get("integration") or self.manifest["integration"]),
            "capability": str(tool["capability"]),
            "side_effect": str(tool["side_effect"]),
        }

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls[name] = self.calls.get(name, 0) + 1
        call_number = self.calls[name]
        if self.script.get("connection_error"):
            raise ReplayToolError(
                "connection_required",
                "Google Analytics is not connected for this synthetic project.",
                connect_url="https://example.invalid/connect/google-analytics",
            )
        if self.script.get("missing_scope"):
            raise ReplayToolError(
                "missing_scope",
                "The connected account does not have analytics.read access.",
            )
        if name == "list_properties":
            return {
                "properties": [self.manifest["property"]],
                "fixed_clock": self.manifest["fixed_clock"],
            }
        if name != "run_report":
            raise ReplayToolError("unknown_tool", f"Unknown replay tool: {name}")
        if self.script.get("rate_limit_once") and call_number == 1:
            raise ReplayToolError(
                "rate_limited",
                "Synthetic GA4 rate limit; retry after 1 second.",
                retry_after_seconds=1,
                retryable=True,
            )
        if self.script.get("invalid_argument_once") and call_number == 1:
            raise ReplayToolError(
                "invalid_argument",
                "sessionConversionRate is incompatible with the requested synthetic dimension; remove it and calculate purchases / sessions.",
                retryable=False,
            )
        return self._run_report(arguments)

    @staticmethod
    def _names(value: Any, field_name: str) -> list[str]:
        if not isinstance(value, list):
            raise ReplayToolError("invalid_argument", f"{field_name} must be an array")
        result: list[str] = []
        for item in value:
            name = item.get("name") if isinstance(item, dict) else item
            if not isinstance(name, str) or not name:
                raise ReplayToolError(
                    "invalid_argument", f"Every {field_name} entry needs a name"
                )
            result.append(name)
        return result

    def _run_report(self, arguments: dict[str, Any]) -> dict[str, Any]:
        property_name = arguments.get("property") or arguments.get("property_id")
        expected_property = self.manifest["property"]["name"]
        if property_name != expected_property:
            raise ReplayToolError(
                "wrong_property",
                f"Use the connected property {expected_property}.",
                requested_property=property_name,
            )
        ranges = arguments.get("dateRanges") or arguments.get("date_ranges")
        if not isinstance(ranges, list) or not ranges:
            raise ReplayToolError("invalid_argument", "dateRanges must be a non-empty array")
        requested_periods: list[str] = []
        known_ranges = self.manifest["date_ranges"]
        for value in ranges:
            if not isinstance(value, dict):
                raise ReplayToolError("invalid_argument", "dateRanges entries must be objects")
            start = value.get("startDate") or value.get("start_date")
            end = value.get("endDate") or value.get("end_date")
            match = next(
                (
                    name
                    for name, known in known_ranges.items()
                    if known["start_date"] == start and known["end_date"] == end
                ),
                None,
            )
            if not match:
                raise ReplayToolError(
                    "unknown_date_range",
                    "The synthetic fixture recognizes only the documented current and previous week.",
                    start_date=start,
                    end_date=end,
                )
            requested_periods.append(match)
        dimensions = self._names(arguments.get("dimensions") or [], "dimensions")
        metrics = self._names(arguments.get("metrics") or [], "metrics")
        allowed_dimensions = {
            "sessionDefaultChannelGroup": "channel",
            "landingPagePlusQueryString": "landing_page",
            "sessionCampaignName": "campaign",
        }
        allowed_metrics = {"sessions", "ecommercePurchases", "sessionConversionRate"}
        unknown_dimensions = sorted(set(dimensions) - set(allowed_dimensions))
        unknown_metrics = sorted(set(metrics) - allowed_metrics)
        if unknown_dimensions or unknown_metrics or not metrics:
            raise ReplayToolError(
                "invalid_argument",
                "Unsupported synthetic GA4 fields.",
                unknown_dimensions=unknown_dimensions,
                unknown_metrics=unknown_metrics,
            )
        rows = [row for row in self.dataset if row["period"] in requested_periods]
        if self.script.get("empty_period"):
            rows = [row for row in rows if row["period"] != self.script["empty_period"]]
        group_fields = [allowed_dimensions[name] for name in dimensions]
        groups: dict[tuple[Any, ...], dict[str, Any]] = {}
        for row in rows:
            key = (row["period"], *(row[field] for field in group_fields))
            aggregate = groups.setdefault(
                key,
                {
                    "period": row["period"],
                    **{field: row[field] for field in group_fields},
                    "sessions": 0,
                    "ecommercePurchases": 0,
                },
            )
            aggregate["sessions"] += int(row["sessions"])
            aggregate["ecommercePurchases"] += int(row["ecommercePurchases"])
        grouped = list(groups.values())
        for row in grouped:
            sessions = row["sessions"]
            row["sessionConversionRate"] = (
                row["ecommercePurchases"] / sessions if sessions else None
            )
        if self.script.get("primary_driver_last"):
            grouped.sort(
                key=lambda row: (
                    row.get("channel") == "Paid Search"
                    and row.get("landing_page") == "/pricing",
                    row["period"],
                )
            )
        else:
            grouped.sort(key=lambda row: (-row["sessions"], row["period"]))
        offset = int(arguments.get("offset") or 0)
        requested_limit = int(arguments.get("limit") or 100)
        max_page_size = int(self.script.get("max_page_size") or requested_limit)
        limit = max(1, min(requested_limit, max_page_size))
        page = grouped[offset : offset + limit]
        response_rows = []
        for row in page:
            response_rows.append(
                {
                    "dateRange": row["period"],
                    "dimensionValues": {
                        name: row[allowed_dimensions[name]] for name in dimensions
                    },
                    "metricValues": {name: row[name] for name in metrics},
                }
            )
        return {
            "dimensionHeaders": dimensions,
            "metricHeaders": metrics,
            "rows": response_rows,
            "rowCount": len(grouped),
            "offset": offset,
            "limit": limit,
            "nextOffset": offset + limit if offset + limit < len(grouped) else None,
            "metadata": {
                "dataLossFromOtherRow": False,
                "currencyCode": "USD",
                "timeZone": "America/Los_Angeles",
                "synthetic": True,
            },
        }


@dataclass
class ReplayCrossToolService:
    fixture_dir: Path
    scenario_id: str

    def __post_init__(self) -> None:
        self.manifest = json.loads((self.fixture_dir / "manifest.json").read_text())
        self.tools = json.loads((self.fixture_dir / "tools.json").read_text())["tools"]
        self.dataset = json.loads((self.fixture_dir / "dataset.json").read_text())
        self.calls: dict[str, int] = {}

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": tool["input_schema"],
            }
            for tool in self.tools
        ]

    def metadata_for(self, name: str) -> dict[str, str]:
        tool = next((tool for tool in self.tools if tool.get("name") == name), None)
        if tool is None:
            raise ReplayToolError("unknown_tool", f"Unknown replay tool: {name}")
        return {
            "operation": str(tool["operation"]),
            "integration": str(tool["integration"]),
            "capability": str(tool["capability"]),
            "side_effect": str(tool["side_effect"]),
        }

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls[name] = self.calls.get(name, 0) + 1
        if name == "list_integrations":
            return {
                "integrations": self.dataset["integrations"],
                "fixed_clock": self.manifest["fixed_clock"],
            }
        source_by_tool = {
            "ga4_summary": "ga4",
            "search_console_query": "search_console",
            "google_ads_search": "google_ads",
            "commerce_summary": "commerce",
            "crm_funnel": "crm",
        }
        source = source_by_tool.get(name)
        if source is None:
            raise ReplayToolError("unknown_tool", f"Unknown replay tool: {name}")
        requested = arguments.get("date_ranges") or arguments.get("dateRanges")
        if not isinstance(requested, list) or len(requested) != 2:
            raise ReplayToolError(
                "invalid_argument",
                "Cross-tool summaries require exactly the documented previous and current periods.",
            )
        observed_ranges: set[tuple[str, str]] = set()
        for value in requested:
            if not isinstance(value, dict):
                raise ReplayToolError(
                    "invalid_argument", "Every date range must be an object."
                )
            observed_ranges.add(
                (
                    str(value.get("start_date") or value.get("startDate") or ""),
                    str(value.get("end_date") or value.get("endDate") or ""),
                )
            )
        expected_ranges = {
            (str(value["start_date"]), str(value["end_date"]))
            for value in self.manifest["date_ranges"].values()
        }
        if observed_ranges != expected_ranges:
            raise ReplayToolError(
                "unknown_date_range",
                "Use the two complete periods documented by the synthetic fixture.",
            )
        result = self.dataset["sources"][source]
        return {
            "source": source,
            "periods": result,
            "synthetic": True,
            "definitions": self.dataset["definitions"].get(source, {}),
        }


def load_service(fixture_dir: Path, scenario_id: str) -> Any:
    manifest = json.loads((fixture_dir / "manifest.json").read_text())
    if manifest.get("service_type") == "cross_tool":
        return ReplayCrossToolService(fixture_dir, scenario_id)
    return ReplayGa4Service(fixture_dir, scenario_id)


class McpServer:
    def __init__(
        self,
        service: Any,
        *,
        attempt_id: str,
        ledger_path: Path,
        stdin: TextIO = sys.stdin,
        stdout: TextIO = sys.stdout,
    ) -> None:
        self.service = service
        self.attempt_id = attempt_id
        self.ledger_path = ledger_path
        self.stdin = stdin
        self.stdout = stdout
        self.sequence = 0

    def _write(self, value: dict[str, Any]) -> None:
        self.stdout.write(json.dumps(value, separators=(",", ":")) + "\n")
        self.stdout.flush()

    def _ledger(self, value: dict[str, Any]) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a") as handle:
            handle.write(json.dumps(value, sort_keys=True) + "\n")

    def _response(self, request_id: Any, result: Any) -> None:
        self._write({"jsonrpc": "2.0", "id": request_id, "result": result})

    def _error(self, request_id: Any, code: int, message: str) -> None:
        self._write(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": code, "message": message},
            }
        )

    def handle(self, request: dict[str, Any]) -> None:
        method = request.get("method")
        request_id = request.get("id")
        if method == "initialize":
            self._response(
                request_id,
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "agent-eval-replay", "version": "1.0.0"},
                },
            )
            return
        if method == "notifications/initialized":
            return
        if method == "ping":
            self._response(request_id, {})
            return
        if method == "tools/list":
            self._response(request_id, {"tools": self.service.list_tools()})
            return
        if method != "tools/call":
            if request_id is not None:
                self._error(request_id, -32601, f"Method not found: {method}")
            return
        params = request.get("params") or {}
        name = str(params.get("name") or "")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            arguments = {}
        self.sequence += 1
        call_id = str(request_id if request_id is not None else self.sequence)
        started = time.monotonic()
        metadata: dict[str, str]
        try:
            metadata = self.service.metadata_for(name)
            result = self.service.call(name, arguments)
            duration_ms = round((time.monotonic() - started) * 1000, 3)
            self._ledger(
                {
                    "trace_version": 2,
                    "sequence": self.sequence,
                    "attempt_id": self.attempt_id,
                    "call_id": call_id,
                    "tool_name": name,
                    **metadata,
                    "side_effect": metadata["side_effect"],
                    "arguments": arguments,
                    "arguments_sha256": _hash(arguments),
                    "status": "completed",
                    "error_kind": None,
                    "result": result,
                    "result_sha256": _hash(result),
                    "duration_ms": duration_ms,
                    "timestamp": _now(),
                }
            )
            text = json.dumps(result, sort_keys=True)
            self._response(
                request_id,
                {
                    "content": [{"type": "text", "text": text}],
                    "structuredContent": result,
                    "isError": False,
                },
            )
        except ReplayToolError as exc:
            duration_ms = round((time.monotonic() - started) * 1000, 3)
            metadata = (
                self.service.metadata_for(name)
                if any(tool.get("name") == name for tool in self.service.tools)
                else {
                    "operation": "unknown",
                    "integration": str(
                        self.service.manifest.get("integration") or "unknown"
                    ),
                    "capability": "unknown",
                    "side_effect": "external_write",
                }
            )
            error = {"kind": exc.kind, "message": str(exc), **exc.details}
            self._ledger(
                {
                    "trace_version": 2,
                    "sequence": self.sequence,
                    "attempt_id": self.attempt_id,
                    "call_id": call_id,
                    "tool_name": name,
                    **metadata,
                    "arguments": arguments,
                    "arguments_sha256": _hash(arguments),
                    "status": "error",
                    "error_kind": exc.kind,
                    "result": error,
                    "result_sha256": _hash(error),
                    "duration_ms": duration_ms,
                    "timestamp": _now(),
                }
            )
            self._response(
                request_id,
                {
                    "content": [
                        {"type": "text", "text": json.dumps(error, sort_keys=True)}
                    ],
                    "structuredContent": error,
                    "isError": True,
                },
            )

    def serve(self) -> None:
        for line in self.stdin:
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    self.handle(value)
            except json.JSONDecodeError:
                continue


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--ledger", required=True, type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    service = load_service(args.fixture.resolve(), args.scenario)
    McpServer(
        service,
        attempt_id=args.attempt_id,
        ledger_path=args.ledger.resolve(),
    ).serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
