from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser
import json
import re
from typing import Any, Iterable
from urllib.parse import urlparse

from tracker.models import JobPosting, ListingVerificationRun
from tracker.services.page_retrieval import RetrievedPage


_SPACE_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-z0-9+#.]+")

_TITLE_STOPWORDS = {
    "a",
    "an",
    "and",
    "at",
    "for",
    "full",
    "hybrid",
    "i",
    "ii",
    "iii",
    "in",
    "job",
    "of",
    "on",
    "onsite",
    "or",
    "position",
    "remote",
    "role",
    "the",
    "time",
    "to",
    "with",
}

_CLOSED_PHRASES = (
    "applications are closed",
    "application window has closed",
    "job has been closed",
    "job is no longer available",
    "job posting is no longer available",
    "no longer accepting applications",
    "position has been filled",
    "position is no longer available",
    "posting has closed",
    "role has been filled",
    "this job is no longer available",
    "this opportunity is no longer available",
    "this position is no longer available",
    "vacancy has been filled",
)

_EXPIRED_PHRASES = (
    "application deadline has passed",
    "job has expired",
    "job posting has expired",
    "opportunity has expired",
    "posting has expired",
    "this job has expired",
)

_GENERIC_CAREERS_PHRASES = (
    "browse all jobs",
    "career opportunities",
    "explore careers",
    "find jobs",
    "job search",
    "join our talent community",
    "search all jobs",
    "search jobs",
    "view all jobs",
)

_ROLLING_DEADLINE_PHRASES = (
    "applications accepted on a rolling basis",
    "applications are reviewed on a rolling basis",
    "open until filled",
    "rolling applications",
    "rolling basis",
)

_NO_DEADLINE_PHRASES = (
    "deadline not specified",
    "no application deadline",
    "no deadline is specified",
    "no deadline specified",
)

_APPLY_TEXT_PATTERNS = (
    re.compile(r"^apply$", re.IGNORECASE),
    re.compile(r"\bapply now\b", re.IGNORECASE),
    re.compile(r"\bapply for (?:this|the) (?:job|role|position)\b", re.IGNORECASE),
    re.compile(r"\bstart (?:an |your )?application\b", re.IGNORECASE),
    re.compile(r"\bsubmit (?:an |your )?application\b", re.IGNORECASE),
)

_DEADLINE_CUE_RE = re.compile(
    r"(?:application deadline|apply by|closing date|applications? (?:close|closes|must be received by)|deadline)"
    r"\s*(?:is|on|:|-)?\s*(.{0,90})",
    re.IGNORECASE,
)

_DATE_PATTERNS = (
    re.compile(r"\b(20\d{2}-\d{1,2}-\d{1,2})\b"),
    re.compile(
        r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+\d{1,2}(?:st|nd|rd|th)?(?:,)?\s+20\d{2})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
        r"\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,)?\s+20\d{2})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+20\d{2})\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(\d{1,2}/\d{1,2}/20\d{2})\b"),
    re.compile(r"\b(\d{1,2}-\d{1,2}-20\d{2})\b"),
)

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%B %d %Y",
    "%b %d %Y",
    "%d %B %Y",
    "%m/%d/%Y",
    "%m-%d-%Y",
)


@dataclass(frozen=True)
class ParsedEmployerPage:
    document_title: str = ""
    visible_text: str = ""
    meta_titles: tuple[str, ...] = ()
    site_names: tuple[str, ...] = ()
    links: tuple[dict[str, str], ...] = ()
    buttons: tuple[str, ...] = ()
    json_ld_documents: tuple[Any, ...] = ()


@dataclass(frozen=True)
class PageInterpretation:
    detected_job_title: str = ""
    detected_company: str = ""
    detected_listing_status: str = JobPosting.ListingStatus.UNVERIFIED
    detected_deadline_status: str = JobPosting.DeadlineStatus.UNKNOWN
    detected_deadline: date | None = None
    apply_action_found: bool | None = None
    confidence: str = ListingVerificationRun.Confidence.UNKNOWN
    evidence: str = ""
    structured_evidence: dict[str, Any] = field(default_factory=dict)


class _EmployerPageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.visible_parts: list[str] = []
        self.meta_titles: list[str] = []
        self.site_names: list[str] = []
        self.links: list[dict[str, str]] = []
        self.buttons: list[str] = []
        self.json_ld_scripts: list[str] = []

        self._title_depth = 0
        self._ignored_depth = 0
        self._json_ld_depth = 0
        self._json_ld_parts: list[str] = []
        self._link_stack: list[dict[str, Any]] = []
        self._button_stack: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs):
        tag = tag.casefold()
        attributes = {str(key).casefold(): value or "" for key, value in attrs}

        if tag == "script":
            script_type = attributes.get("type", "").split(";", 1)[0].strip().casefold()
            if script_type == "application/ld+json":
                self._json_ld_depth += 1
                if self._json_ld_depth == 1:
                    self._json_ld_parts = []
            else:
                self._ignored_depth += 1
            return

        if tag in {"style", "noscript", "template", "svg"}:
            self._ignored_depth += 1
            return

        if tag == "title":
            self._title_depth += 1

        if tag == "meta":
            key = (
                attributes.get("property")
                or attributes.get("name")
                or attributes.get("itemprop")
            ).strip().casefold()
            content = _collapse(attributes.get("content", ""))
            if content and key in {"og:title", "twitter:title", "title"}:
                self.meta_titles.append(content)
            if content and key in {"og:site_name", "application-name", "site_name"}:
                self.site_names.append(content)

        if tag == "a":
            self._link_stack.append(
                {
                    "href": attributes.get("href", "").strip(),
                    "parts": [],
                }
            )

        if tag == "button":
            self._button_stack.append([])

        if tag == "input":
            input_type = attributes.get("type", "").casefold()
            value = _collapse(attributes.get("value", ""))
            if value and input_type in {"button", "submit"}:
                self.buttons.append(value)

    def handle_endtag(self, tag: str):
        tag = tag.casefold()

        if tag == "script":
            if self._json_ld_depth:
                self._json_ld_depth -= 1
                if self._json_ld_depth == 0:
                    script = "".join(self._json_ld_parts).strip()
                    if script:
                        self.json_ld_scripts.append(script)
                    self._json_ld_parts = []
            elif self._ignored_depth:
                self._ignored_depth -= 1
            return

        if tag in {"style", "noscript", "template", "svg"}:
            if self._ignored_depth:
                self._ignored_depth -= 1
            return

        if tag == "title" and self._title_depth:
            self._title_depth -= 1

        if tag == "a" and self._link_stack:
            item = self._link_stack.pop()
            text = _collapse(" ".join(item["parts"]))
            self.links.append({"text": text, "href": item["href"]})

        if tag == "button" and self._button_stack:
            parts = self._button_stack.pop()
            text = _collapse(" ".join(parts))
            if text:
                self.buttons.append(text)

    def handle_data(self, data: str):
        if self._json_ld_depth:
            self._json_ld_parts.append(data)
            return
        if self._ignored_depth:
            return

        value = _collapse(data)
        if not value:
            return

        if self._title_depth:
            self.title_parts.append(value)
        self.visible_parts.append(value)

        if self._link_stack:
            self._link_stack[-1]["parts"].append(value)
        if self._button_stack:
            self._button_stack[-1].append(value)

    def parsed(self) -> ParsedEmployerPage:
        json_documents: list[Any] = []
        for script in self.json_ld_scripts:
            try:
                json_documents.append(json.loads(script))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue

        return ParsedEmployerPage(
            document_title=_collapse(" ".join(self.title_parts)),
            visible_text=_collapse(" ".join(self.visible_parts)),
            meta_titles=tuple(_unique(self.meta_titles)),
            site_names=tuple(_unique(self.site_names)),
            links=tuple(self.links),
            buttons=tuple(_unique(self.buttons)),
            json_ld_documents=tuple(json_documents),
        )


class EmployerPageInterpreter:
    """Deterministically interpret one bounded employer-page retrieval.

    The interpreter only reports evidence found in the retrieved response. It does
    not update the current job record and does not treat missing evidence as proof.
    """

    version = "3.4-deterministic-page-interpretation-v1"

    def interpret(
        self,
        job: JobPosting,
        page: RetrievedPage,
        *,
        today: date | None = None,
    ) -> PageInterpretation:
        today = today or date.today()
        parsed = self._parse(page)
        visible_normalized = _normalize(parsed.visible_text)

        json_jobs = list(_iter_job_postings(parsed.json_ld_documents))
        title_candidates = self._title_candidates(parsed, json_jobs)
        company_candidates = self._company_candidates(parsed, json_jobs)

        detected_title, title_source, title_score = _best_candidate(
            job.title,
            title_candidates,
        )
        detected_company, company_source, company_score = _best_candidate(
            job.company,
            company_candidates,
        )

        expected_title_normalized = _normalize(job.title)
        if expected_title_normalized and expected_title_normalized in visible_normalized:
            if title_score < 0.92:
                detected_title = detected_title or job.title
                title_source = title_source or "visible_exact_phrase"
                title_score = 0.92

        expected_company_normalized = _normalize_company(job.company)
        if expected_company_normalized and expected_company_normalized in _normalize_company(
            parsed.visible_text
        ):
            if company_score < 0.9:
                detected_company = detected_company or job.company
                company_source = company_source or "visible_exact_phrase"
                company_score = 0.9

        apply_actions = self._apply_actions(parsed, json_jobs)
        apply_action_found = bool(apply_actions)

        closed_signals = _matching_phrases(visible_normalized, _CLOSED_PHRASES)
        expired_signals = _matching_phrases(visible_normalized, _EXPIRED_PHRASES)
        generic_page_signals = _matching_phrases(
            visible_normalized,
            _GENERIC_CAREERS_PHRASES,
        )

        deadline_status, detected_deadline, deadline_evidence = self._deadline(
            parsed,
            json_jobs,
            today=today,
        )
        if detected_deadline and detected_deadline < today:
            expired_signals.append(
                f"confirmed deadline passed on {detected_deadline.isoformat()}"
            )

        generic_final_url = _looks_like_generic_careers_url(page.final_url)
        wrong_page_signals: list[str] = []
        if title_score < 0.45 and generic_page_signals:
            wrong_page_signals.append("generic careers or job-search page without a role match")
        if title_score < 0.45 and generic_final_url:
            wrong_page_signals.append("final URL looks like a careers home or search page")
        if (
            title_candidates
            and title_score < 0.35
            and any(source in {"json_ld", "document_title", "meta_title"} for _, source in title_candidates)
        ):
            wrong_page_signals.append("page-level title evidence does not match the saved role")

        json_role_match = any(
            _similarity(job.title, _text(item.get("title"))) >= 0.65
            for item in json_jobs
        )
        json_company_match = any(
            _similarity(
                job.company,
                _organization_name(item.get("hiringOrganization")),
                company=True,
            )
            >= 0.55
            for item in json_jobs
        )
        valid_json_job = json_role_match and json_company_match

        listing_status, confidence, classification_reasons = self._classify(
            page=page,
            title_score=title_score,
            company_score=company_score,
            apply_action_found=apply_action_found,
            valid_json_job=valid_json_job,
            closed_signals=closed_signals,
            expired_signals=expired_signals,
            wrong_page_signals=wrong_page_signals,
        )

        evidence = self._evidence_summary(
            listing_status=listing_status,
            confidence=confidence,
            title_score=title_score,
            company_score=company_score,
            apply_action_found=apply_action_found,
            classification_reasons=classification_reasons,
            deadline_status=deadline_status,
            detected_deadline=detected_deadline,
        )

        structured = {
            "interpretation_performed": True,
            "interpreter_version": self.version,
            "page_document_title": parsed.document_title,
            "meta_titles": list(parsed.meta_titles),
            "site_names": list(parsed.site_names),
            "detected_job_title": detected_title,
            "detected_job_title_source": title_source,
            "role_match_score": round(title_score, 4),
            "detected_company": detected_company,
            "detected_company_source": company_source,
            "company_match_score": round(company_score, 4),
            "json_ld_job_count": len(json_jobs),
            "json_ld_role_match": json_role_match,
            "json_ld_company_match": json_company_match,
            "apply_action_found": apply_action_found,
            "apply_actions": apply_actions[:12],
            "closed_signals": closed_signals,
            "expired_signals": expired_signals,
            "generic_page_signals": generic_page_signals,
            "wrong_page_signals": wrong_page_signals,
            "deadline_evidence": deadline_evidence,
            "classification_reasons": classification_reasons,
            "visible_text_preview": parsed.visible_text[:2500],
            "next_required_capability": "review_and_apply_interpretation",
        }

        return PageInterpretation(
            detected_job_title=detected_title,
            detected_company=detected_company,
            detected_listing_status=listing_status,
            detected_deadline_status=deadline_status,
            detected_deadline=detected_deadline,
            apply_action_found=apply_action_found,
            confidence=confidence,
            evidence=evidence,
            structured_evidence=structured,
        )

    @staticmethod
    def _parse(page: RetrievedPage) -> ParsedEmployerPage:
        if not page.body_stored or not page.body_text.strip():
            return ParsedEmployerPage()
        if page.content_type == "text/plain":
            text = _collapse(page.body_text)
            return ParsedEmployerPage(visible_text=text)

        parser = _EmployerPageParser()
        parser.feed(page.body_text)
        parser.close()
        return parser.parsed()

    @staticmethod
    def _title_candidates(
        parsed: ParsedEmployerPage,
        json_jobs: list[dict[str, Any]],
    ) -> list[tuple[str, str]]:
        candidates: list[tuple[str, str]] = []
        for item in json_jobs:
            title = _text(item.get("title"))
            if title:
                candidates.append((title, "json_ld"))
        for title in parsed.meta_titles:
            candidates.append((title, "meta_title"))
        if parsed.document_title:
            candidates.append((parsed.document_title, "document_title"))
            for segment in re.split(r"\s+[|–—]\s+|\s+-\s+", parsed.document_title):
                segment = _collapse(segment)
                if segment and segment != parsed.document_title:
                    candidates.append((segment, "document_title"))
        return _unique_candidates(candidates)

    @staticmethod
    def _company_candidates(
        parsed: ParsedEmployerPage,
        json_jobs: list[dict[str, Any]],
    ) -> list[tuple[str, str]]:
        candidates: list[tuple[str, str]] = []
        for item in json_jobs:
            company = _organization_name(item.get("hiringOrganization"))
            if company:
                candidates.append((company, "json_ld"))
        for name in parsed.site_names:
            candidates.append((name, "site_name"))
        return _unique_candidates(candidates)

    @staticmethod
    def _apply_actions(
        parsed: ParsedEmployerPage,
        json_jobs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        for link in parsed.links:
            text = _collapse(link.get("text", ""))
            href = link.get("href", "").strip()
            normalized_href = href.casefold()
            text_match = any(pattern.search(text) for pattern in _APPLY_TEXT_PATTERNS)
            href_match = bool(
                re.search(r"(?:^|[/_-])(apply|application)(?:[/_?=&-]|$)", normalized_href)
            )
            if text_match or (href_match and "apply" in _normalize(text)):
                actions.append({"source": "link", "text": text, "href": href})

        for text in parsed.buttons:
            if any(pattern.search(text) for pattern in _APPLY_TEXT_PATTERNS):
                actions.append({"source": "button", "text": text, "href": ""})

        for item in json_jobs:
            if item.get("directApply") is True:
                actions.append(
                    {
                        "source": "json_ld",
                        "text": "directApply=true",
                        "href": _text(item.get("url")),
                    }
                )

        unique: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for action in actions:
            key = (
                str(action.get("source", "")),
                str(action.get("text", "")),
                str(action.get("href", "")),
            )
            if key not in seen:
                seen.add(key)
                unique.append(action)
        return unique

    @staticmethod
    def _deadline(
        parsed: ParsedEmployerPage,
        json_jobs: list[dict[str, Any]],
        *,
        today: date,
    ) -> tuple[str, date | None, list[str]]:
        evidence: list[str] = []
        json_dates: list[date] = []
        for item in json_jobs:
            raw = _text(item.get("validThrough"))
            parsed_date = _parse_date(raw)
            if parsed_date:
                json_dates.append(parsed_date)
                evidence.append(f"JSON-LD validThrough={parsed_date.isoformat()}")

        if json_dates:
            selected = min(json_dates)
            return JobPosting.DeadlineStatus.CONFIRMED, selected, evidence

        normalized = _normalize(parsed.visible_text)
        rolling = _matching_phrases(normalized, _ROLLING_DEADLINE_PHRASES)
        if rolling:
            return JobPosting.DeadlineStatus.ROLLING, None, rolling

        not_stated = _matching_phrases(normalized, _NO_DEADLINE_PHRASES)
        if not_stated:
            return JobPosting.DeadlineStatus.NOT_STATED, None, not_stated

        for cue_match in _DEADLINE_CUE_RE.finditer(parsed.visible_text):
            fragment = cue_match.group(1)
            parsed_date, raw_date = _find_date(fragment)
            if parsed_date:
                evidence.append(f"deadline phrase contained {raw_date}")
                return JobPosting.DeadlineStatus.CONFIRMED, parsed_date, evidence

        return JobPosting.DeadlineStatus.UNKNOWN, None, evidence

    @staticmethod
    def _classify(
        *,
        page: RetrievedPage,
        title_score: float,
        company_score: float,
        apply_action_found: bool,
        valid_json_job: bool,
        closed_signals: list[str],
        expired_signals: list[str],
        wrong_page_signals: list[str],
    ) -> tuple[str, str, list[str]]:
        reasons: list[str] = []

        if expired_signals:
            reasons.extend(expired_signals)
            confidence = (
                ListingVerificationRun.Confidence.HIGH
                if title_score >= 0.65 or any("deadline passed" in item for item in expired_signals)
                else ListingVerificationRun.Confidence.MEDIUM
            )
            return JobPosting.ListingStatus.EXPIRED, confidence, reasons

        if closed_signals:
            reasons.extend(closed_signals)
            confidence = (
                ListingVerificationRun.Confidence.HIGH
                if title_score >= 0.65
                else ListingVerificationRun.Confidence.MEDIUM
            )
            return JobPosting.ListingStatus.CLOSED, confidence, reasons

        if page.status_code in {404, 410}:
            reasons.append(f"employer page returned HTTP {page.status_code}")
            return (
                JobPosting.ListingStatus.LINK_BROKEN,
                ListingVerificationRun.Confidence.HIGH,
                reasons,
            )

        if wrong_page_signals:
            reasons.extend(wrong_page_signals)
            return (
                JobPosting.ListingStatus.WRONG_PAGE,
                ListingVerificationRun.Confidence.MEDIUM,
                reasons,
            )

        role_match = title_score >= 0.65
        company_match = company_score >= 0.55
        successful_response = 200 <= page.status_code < 400
        open_evidence = apply_action_found or valid_json_job
        if successful_response and role_match and company_match and open_evidence:
            if apply_action_found:
                reasons.append("matching role and company with an application action")
            if valid_json_job:
                reasons.append("matching structured JobPosting data")
            confidence = (
                ListingVerificationRun.Confidence.HIGH
                if apply_action_found and valid_json_job
                else ListingVerificationRun.Confidence.MEDIUM
            )
            return JobPosting.ListingStatus.OPEN, confidence, reasons

        if page.status_code >= 400:
            reasons.append(f"HTTP {page.status_code} did not establish listing availability")
        if not role_match:
            reasons.append("saved role was not matched strongly enough")
        if not company_match:
            reasons.append("saved company was not matched strongly enough")
        if not open_evidence:
            reasons.append("no reliable application action or structured JobPosting was found")
        return (
            JobPosting.ListingStatus.UNVERIFIED,
            ListingVerificationRun.Confidence.LOW,
            reasons,
        )

    @staticmethod
    def _evidence_summary(
        *,
        listing_status: str,
        confidence: str,
        title_score: float,
        company_score: float,
        apply_action_found: bool,
        classification_reasons: list[str],
        deadline_status: str,
        detected_deadline: date | None,
    ) -> str:
        listing_label = dict(JobPosting.ListingStatus.choices).get(
            listing_status,
            "Unverified",
        )
        confidence_label = dict(ListingVerificationRun.Confidence.choices).get(
            confidence,
            "Not assessed",
        )
        reason_text = "; ".join(classification_reasons[:4]) or "evidence was inconclusive"
        deadline_text = dict(JobPosting.DeadlineStatus.choices).get(
            deadline_status,
            "Unknown",
        )
        if detected_deadline:
            deadline_text = f"{deadline_text} ({detected_deadline.isoformat()})"
        return (
            f"Deterministic page interpretation suggests {listing_label} with "
            f"{confidence_label.lower()} confidence. Role match {title_score:.0%}; "
            f"company match {company_score:.0%}; application action "
            f"{'found' if apply_action_found else 'not found'}; deadline {deadline_text}. "
            f"Evidence: {reason_text}. Review is required before updating the job record."
        )


def _collapse(value: Any) -> str:
    return _SPACE_RE.sub(" ", str(value or "")).strip()


def _normalize(value: Any) -> str:
    return _collapse(value).casefold()


def _normalize_company(value: Any) -> str:
    normalized = _normalize(value)
    normalized = re.sub(
        r"\b(?:incorporated|inc|corporation|corp|company|co|limited|ltd|llc|plc)\b\.?",
        " ",
        normalized,
    )
    return _collapse(normalized)


def _tokens(value: Any, *, company: bool = False) -> set[str]:
    normalized = _normalize_company(value) if company else _normalize(value)
    tokens = set(_TOKEN_RE.findall(normalized))
    if not company:
        tokens -= _TITLE_STOPWORDS
    return tokens


def _similarity(expected: Any, candidate: Any, *, company: bool = False) -> float:
    expected_text = _normalize_company(expected) if company else _normalize(expected)
    candidate_text = _normalize_company(candidate) if company else _normalize(candidate)
    if not expected_text or not candidate_text:
        return 0.0
    if expected_text == candidate_text:
        return 1.0
    if expected_text in candidate_text or candidate_text in expected_text:
        shorter = min(len(expected_text), len(candidate_text))
        longer = max(len(expected_text), len(candidate_text))
        return max(0.82, shorter / longer)

    expected_tokens = _tokens(expected_text, company=company)
    candidate_tokens = _tokens(candidate_text, company=company)
    if not expected_tokens or not candidate_tokens:
        return 0.0
    overlap = expected_tokens & candidate_tokens
    coverage = len(overlap) / len(expected_tokens)
    precision = len(overlap) / len(candidate_tokens)
    return round((coverage * 0.7) + (precision * 0.3), 4)


def _best_candidate(
    expected: str,
    candidates: Iterable[tuple[str, str]],
) -> tuple[str, str, float]:
    best_text = ""
    best_source = ""
    best_score = 0.0
    company = "company" in expected.casefold() and False
    for text, source in candidates:
        score = _similarity(expected, text, company=company)
        if score > best_score:
            best_text = text
            best_source = source
            best_score = score
    return best_text, best_source, best_score


def _organization_name(value: Any) -> str:
    if isinstance(value, dict):
        return _text(value.get("name"))
    return _text(value)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float)):
        return _collapse(value)
    return ""


def _iter_job_postings(values: Iterable[Any]):
    for value in values:
        yield from _walk_job_postings(value)


def _walk_job_postings(value: Any):
    if isinstance(value, list):
        for item in value:
            yield from _walk_job_postings(item)
        return
    if not isinstance(value, dict):
        return

    raw_type = value.get("@type")
    types = raw_type if isinstance(raw_type, list) else [raw_type]
    if any(str(item).casefold() == "jobposting" for item in types if item):
        yield value

    for key, child in value.items():
        if key in {"description", "title"}:
            continue
        if isinstance(child, (dict, list)):
            yield from _walk_job_postings(child)


def _matching_phrases(normalized_text: str, phrases: Iterable[str]) -> list[str]:
    return [phrase for phrase in phrases if phrase in normalized_text]


def _parse_date(value: str) -> date | None:
    raw = _collapse(value)
    if not raw:
        return None
    iso_candidate = raw[:10]
    try:
        return date.fromisoformat(iso_candidate)
    except ValueError:
        pass

    cleaned = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", raw, flags=re.IGNORECASE)
    cleaned = cleaned.replace(",", "").replace("Sept.", "Sep").replace("Sept ", "Sep ")
    cleaned = cleaned.replace(".", "")
    for date_format in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, date_format).date()
        except ValueError:
            continue
    return None


def _find_date(fragment: str) -> tuple[date | None, str]:
    for pattern in _DATE_PATTERNS:
        match = pattern.search(fragment)
        if not match:
            continue
        raw = match.group(1)
        parsed = _parse_date(raw)
        if parsed:
            return parsed, raw
    return None, ""


def _looks_like_generic_careers_url(url: str) -> bool:
    parsed = urlparse(url or "")
    path = parsed.path.strip("/").casefold()
    if not path:
        return True
    exact_paths = {
        "career",
        "careers",
        "job-search",
        "jobs",
        "search",
        "search-jobs",
    }
    if path in exact_paths:
        return True
    segments = [segment for segment in path.split("/") if segment]
    return bool(segments and segments[-1] in {"careers", "jobs", "search"})


def _unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _normalize(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(value)
    return result


def _unique_candidates(
    candidates: Iterable[tuple[str, str]],
) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for text, source in candidates:
        key = (_normalize(text), source)
        if key[0] and key not in seen:
            seen.add(key)
            result.append((text, source))
    return result
