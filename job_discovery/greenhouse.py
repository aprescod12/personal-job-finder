from __future__ import annotations

import json
import re
import socket
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings

from .providers import DiscoveryQuery, DiscoveredOpportunity


GREENHOUSE_API_ROOT = "https://boards-api.greenhouse.io/v1/boards"
_BOARD_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_BLOCK_TAGS = {
    "address",
    "article",
    "blockquote",
    "br",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "ol",
    "p",
    "section",
    "table",
    "tr",
    "ul",
}


class GreenhouseDiscoveryError(RuntimeError):
    pass


class GreenhouseDiscoveryConfigurationError(GreenhouseDiscoveryError):
    pass


class GreenhouseBoardRequestError(GreenhouseDiscoveryError):
    pass


@dataclass(frozen=True)
class GreenhouseBoard:
    key: str
    label: str
    board_token: str
    industry_hint: str = ""


class _HTMLToTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        del attrs
        tag = tag.casefold()
        if tag == "li":
            self.parts.append("\n- ")
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str):
        if tag.casefold() in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str):
        self.parts.append(data)

    def text(self) -> str:
        raw = "".join(self.parts).replace("\xa0", " ")
        lines = []
        blank_pending = False
        for raw_line in raw.splitlines():
            line = re.sub(r"[ \t]+", " ", raw_line).strip()
            if not line:
                blank_pending = bool(lines)
                continue
            if blank_pending:
                lines.append("")
                blank_pending = False
            lines.append(line)
        return "\n".join(lines).strip()


def greenhouse_html_to_text(value: str) -> str:
    parser = _HTMLToTextParser()
    parser.feed(value or "")
    parser.close()
    return parser.text()


def _positive_setting(name: str, default: int) -> int:
    value = getattr(settings, name, default)
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _nonnegative_setting(name: str, default: int) -> int:
    value = getattr(settings, name, default)
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    return value if value >= 0 else default


def configured_greenhouse_boards() -> tuple[GreenhouseBoard, ...]:
    raw_boards = getattr(settings, "GREENHOUSE_DISCOVERY_BOARDS", [])
    if isinstance(raw_boards, str):
        try:
            raw_boards = json.loads(raw_boards)
        except json.JSONDecodeError as exc:
            raise GreenhouseDiscoveryConfigurationError(
                "GREENHOUSE_DISCOVERY_BOARDS must be valid JSON."
            ) from exc
    if not isinstance(raw_boards, (list, tuple)):
        raise GreenhouseDiscoveryConfigurationError(
            "GREENHOUSE_DISCOVERY_BOARDS must be a list of approved board records."
        )

    boards: list[GreenhouseBoard] = []
    seen_keys: set[str] = set()
    seen_tokens: set[str] = set()
    max_boards = _positive_setting("GREENHOUSE_DISCOVERY_MAX_BOARDS", 5)

    for item in raw_boards:
        if not isinstance(item, dict) or not item.get("enabled", True):
            continue
        key = str(item.get("key", "")).strip()
        label = str(item.get("label", "")).strip()
        token = str(item.get("board_token", "")).strip()
        industry_hint = str(item.get("industry_hint", "")).strip()
        if not key or not label or not token:
            raise GreenhouseDiscoveryConfigurationError(
                "Every enabled Greenhouse board needs key, label, and board_token."
            )
        if not _BOARD_TOKEN_PATTERN.fullmatch(token):
            raise GreenhouseDiscoveryConfigurationError(
                f"Greenhouse board token {token!r} contains unsupported characters."
            )
        if key in seen_keys or token.casefold() in seen_tokens:
            raise GreenhouseDiscoveryConfigurationError(
                "Greenhouse board keys and tokens must be unique."
            )
        seen_keys.add(key)
        seen_tokens.add(token.casefold())
        boards.append(
            GreenhouseBoard(
                key=key,
                label=label,
                board_token=token,
                industry_hint=industry_hint,
            )
        )
        if len(boards) >= max_boards:
            break

    if not boards:
        raise GreenhouseDiscoveryConfigurationError(
            "No enabled Greenhouse employer boards are configured."
        )
    return tuple(boards)


def _request_json(url: str) -> dict[str, Any]:
    timeout = _positive_setting("GREENHOUSE_DISCOVERY_TIMEOUT_SECONDS", 10)
    retry_count = min(_nonnegative_setting("GREENHOUSE_DISCOVERY_RETRY_COUNT", 1), 2)
    user_agent = str(
        getattr(
            settings,
            "GREENHOUSE_DISCOVERY_USER_AGENT",
            "AmirisJobFinder/1.0 controlled-discovery",
        )
    ).strip()
    last_error: Exception | None = None

    for attempt in range(retry_count + 1):
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": user_agent,
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                status = int(getattr(response, "status", 200))
                if status != 200:
                    raise GreenhouseBoardRequestError(
                        f"Greenhouse returned HTTP {status}."
                    )
                payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, dict):
                    raise GreenhouseBoardRequestError(
                        "Greenhouse returned an unexpected response shape."
                    )
                return payload
        except HTTPError as exc:
            last_error = exc
            retryable = exc.code >= 500 or exc.code == 429
            if not retryable or attempt >= retry_count:
                break
        except (URLError, socket.timeout, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt >= retry_count:
                break
        except GreenhouseBoardRequestError as exc:
            last_error = exc
            break
        time.sleep(0.2 * (attempt + 1))

    message = str(last_error) if last_error else "Unknown Greenhouse request failure."
    raise GreenhouseBoardRequestError(message)


def _names(items: Any, key: str = "name") -> list[str]:
    if not isinstance(items, list):
        return []
    values = []
    for item in items:
        if isinstance(item, dict):
            value = str(item.get(key, "")).strip()
            if value and value not in values:
                values.append(value)
    return values


def _job_to_opportunity(board: GreenhouseBoard, job: dict[str, Any]):
    job_id = str(job.get("id", "")).strip()
    title = str(job.get("title", "")).strip()
    source_url = str(job.get("absolute_url", "")).strip()
    location = ""
    location_data = job.get("location")
    if isinstance(location_data, dict):
        location = str(location_data.get("name", "")).strip()
    departments = _names(job.get("departments"))
    offices = _names(job.get("offices"))
    description_html = str(job.get("content", "") or "")
    description_text = greenhouse_html_to_text(description_html)

    header = [title, board.label]
    if location:
        header.append(location)
    if departments:
        header.append(f"Departments: {', '.join(departments)}")
    if offices:
        header.append(f"Offices: {', '.join(offices)}")
    raw_text = "\n".join(header)
    if description_text:
        raw_text = f"{raw_text}\n\n{description_text}"

    if not job_id or not title or not source_url:
        raise GreenhouseBoardRequestError(
            "A published Greenhouse job was missing id, title, or absolute_url."
        )

    metadata = {
        "board_key": board.key,
        "board_label": board.label,
        "board_token": board.board_token,
        "greenhouse_job_post_id": job_id,
        "internal_job_id": job.get("internal_job_id"),
        "updated_at": job.get("updated_at"),
        "language": job.get("language"),
        "departments": job.get("departments", []),
        "offices": job.get("offices", []),
        "location": job.get("location", {}),
        "raw_content_html": description_html,
        "metadata": job.get("metadata"),
    }
    return DiscoveredOpportunity(
        external_id=f"{board.key}:{job_id}",
        source_url=source_url,
        title_hint=title,
        company_hint=board.label,
        location_hint=location,
        raw_listing_text=raw_text,
        industry_hint=board.industry_hint,
        metadata=metadata,
    )


class GreenhouseDiscoveryProvider:
    """Curated, read-only Greenhouse Job Board API provider."""

    key = "greenhouse"
    label = "Greenhouse approved employer boards"
    version = "greenhouse-job-board-v1"

    def __init__(self):
        self.source_reports: list[dict[str, Any]] = []

    def discover(self, query: DiscoveryQuery):
        del query  # Broad preference labeling remains in the discovery service.
        if not bool(getattr(settings, "JOB_DISCOVERY_LIVE_ENABLED", False)):
            raise GreenhouseDiscoveryConfigurationError(
                "Live job discovery is disabled. Set JOB_DISCOVERY_LIVE_ENABLED=true deliberately."
            )

        boards = configured_greenhouse_boards()
        max_jobs = _positive_setting("GREENHOUSE_DISCOVERY_MAX_JOBS_PER_BOARD", 100)
        opportunities: list[DiscoveredOpportunity] = []

        for board in boards:
            started = time.monotonic()
            url = (
                f"{GREENHOUSE_API_ROOT}/{quote(board.board_token, safe='')}/jobs"
                "?content=true"
            )
            try:
                payload = _request_json(url)
                jobs = payload.get("jobs", [])
                if not isinstance(jobs, list):
                    raise GreenhouseBoardRequestError(
                        "Greenhouse response did not contain a jobs list."
                    )
                jobs = sorted(
                    (job for job in jobs if isinstance(job, dict)),
                    key=lambda item: str(item.get("updated_at", "")),
                    reverse=True,
                )[:max_jobs]
                board_opportunities = [
                    _job_to_opportunity(board, job) for job in jobs
                ]
            except Exception as exc:
                self.source_reports.append(
                    {
                        "source_key": board.key,
                        "source_label": board.label,
                        "source_identifier": board.board_token,
                        "status": "failed",
                        "result_count": 0,
                        "error_message": str(exc),
                        "elapsed_ms": round((time.monotonic() - started) * 1000),
                        "metadata": {"request_url": url},
                    }
                )
                continue

            opportunities.extend(board_opportunities)
            self.source_reports.append(
                {
                    "source_key": board.key,
                    "source_label": board.label,
                    "source_identifier": board.board_token,
                    "status": "success",
                    "result_count": len(board_opportunities),
                    "error_message": "",
                    "elapsed_ms": round((time.monotonic() - started) * 1000),
                    "metadata": {
                        "request_url": url,
                        "provider_total": payload.get("meta", {}).get("total")
                        if isinstance(payload.get("meta"), dict)
                        else None,
                        "external_ids": [item.external_id for item in board_opportunities],
                    },
                }
            )

        return tuple(opportunities)
