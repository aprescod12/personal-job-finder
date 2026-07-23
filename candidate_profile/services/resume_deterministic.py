import re
from collections import defaultdict

from .resume_extraction import BaseResumeExtractor, ResumeExtractionRequest


PARSER_VERSION = "deterministic-resume-v2"

_SECTION_ALIASES = {
    "summary": "summary",
    "professional summary": "summary",
    "profile": "summary",
    "objective": "summary",
    "education": "education",
    "academic background": "education",
    "experience": "experience",
    "professional experience": "experience",
    "research and professional experience": "experience",
    "research experience": "experience",
    "work experience": "experience",
    "employment": "experience",
    "projects": "projects",
    "selected projects": "projects",
    "technical projects": "projects",
    "skills": "skills",
    "skill s": "skills",
    "technical skills": "skills",
    "core skills": "skills",
    "certifications": "certifications",
    "licenses and certifications": "certifications",
    "leadership": "leadership",
    "leadership and activities": "leadership",
    "activities": "leadership",
    "organizations": "leadership",
    "relevant coursework": "coursework",
    "coursework": "coursework",
}

_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d().\s-]{7,}\d)(?!\w)")
_LINK_PATTERN = re.compile(
    r"(?:https?://[^\s|]+|(?:linkedin\.com|github\.com)/[^\s|]+)",
    re.IGNORECASE,
)
_LOCATION_PATTERN = re.compile(
    r"\b[A-Za-z][A-Za-z .'-]{1,50},\s*[A-Z]{2}\b"
)
_DATE_PATTERN = re.compile(
    r"\b(?:19|20)\d{2}\b|\b(?:present|current|expected)\b|"
    r"\b(?:spring|summer|fall|autumn|winter)\b|"
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\b",
    re.IGNORECASE,
)


def _clean_line(value: str) -> str:
    value = re.sub(r"^[\s\-–—•*▪◦]+", "", value or "")
    return re.sub(r"\s+", " ", value).strip()


def _normalized_heading(value: str) -> str:
    value = _clean_line(value).casefold()
    value = re.sub(r"\s*[_=]{3,}\s*$", "", value)
    value = value.rstrip(":").replace("&", " and ")
    value = re.sub(r"[^a-z0-9 /-]+", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _sectionize(text: str):
    sections = defaultdict(list)
    current = "header"

    for raw_line in (text or "").splitlines():
        line = _clean_line(raw_line)
        if not line:
            if sections[current] and sections[current][-1] is not None:
                sections[current].append(None)
            continue

        heading = _SECTION_ALIASES.get(_normalized_heading(line))
        if heading:
            current = heading
            continue
        sections[current].append(line)

    return sections


def _blocks(lines):
    blocks = []
    current = []
    for line in lines:
        if line is None:
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line)
    if current:
        blocks.append(current)
    return blocks


def _split_dates(value: str) -> tuple[str, str]:
    matches = list(_DATE_PATTERN.finditer(value or ""))
    if not matches:
        return (value or "").strip(), ""

    start = matches[0].start()
    prefix = (value or "")[:start].rstrip(" |,-–—")
    dates = (value or "")[start:].strip(" |,-–—")
    return prefix.strip(), dates.strip()


def _split_pipe(value: str) -> tuple[str, str]:
    if "|" not in value:
        return value.strip(), ""
    left, right = value.split("|", 1)
    return left.strip(), right.strip()


def _is_detail_line(value: str) -> bool:
    return bool(
        not value
        or value.startswith(("http://", "https://"))
        or value[:1].islower()
    )


def _generic_entries(lines):
    entries = []
    for block in _blocks(lines):
        cleaned_block = [_clean_line(line) for line in block if _clean_line(line)]
        if not cleaned_block:
            continue

        source_text = "\n".join(cleaned_block)
        primary = cleaned_block[0]
        primary_without_dates, dates = _split_dates(primary)
        heading, subheading = _split_pipe(primary_without_dates)
        consumed = {0}

        if len(cleaned_block) > 1 and not subheading:
            candidate = cleaned_block[1]
            if not _is_detail_line(candidate):
                candidate_without_dates, candidate_dates = _split_dates(candidate)
                candidate_heading, candidate_subheading = _split_pipe(
                    candidate_without_dates
                )
                subheading = candidate_heading
                if candidate_subheading:
                    subheading = candidate_heading
                    dates = dates or candidate_subheading
                dates = dates or candidate_dates
                consumed.add(1)

        if not dates:
            for line in cleaned_block:
                _, candidate_dates = _split_dates(line)
                if candidate_dates:
                    dates = candidate_dates
                    break

        details = [
            line
            for index, line in enumerate(cleaned_block)
            if index not in consumed and line != dates
        ]
        entries.append(
            {
                "heading": heading or primary,
                "subheading": subheading,
                "dates": dates,
                "details": details,
                "source_text": source_text,
            }
        )
    return entries


def _dedupe(values):
    output = []
    seen = set()
    for value in values:
        value = (value or "").strip(" ,;|•")
        key = value.casefold()
        if value and key not in seen:
            output.append(value)
            seen.add(key)
    return output


def _extract_skills(lines):
    skills = []
    for line in lines:
        if line is None:
            continue
        value = line
        if ":" in value:
            _, value = value.split(":", 1)
        pieces = re.split(r"\s*[;,|•]\s*", value)
        if len(pieces) == 1:
            pieces = [value]
        skills.extend(pieces)
    return _dedupe(skills)


def _looks_like_name(value: str) -> bool:
    value = _clean_line(value)
    if not 2 <= len(value) <= 80:
        return False
    if any(character.isdigit() for character in value):
        return False
    if any(marker in value for marker in ("@", "|", ":", "/")):
        return False
    if _normalized_heading(value) in _SECTION_ALIASES:
        return False

    words = value.split()
    if not 2 <= len(words) <= 6:
        return False
    return all(re.fullmatch(r"[A-Za-z][A-Za-z.'-]*", word) for word in words)


def _header_values(header_lines):
    lines = [line for line in header_lines if line]
    joined = " | ".join(lines[:12])

    email_match = _EMAIL_PATTERN.search(joined)
    phone_match = _PHONE_PATTERN.search(joined)
    location_match = _LOCATION_PATTERN.search(joined)
    links = _dedupe(_LINK_PATTERN.findall(joined))

    full_name = ""
    for line in lines[:8]:
        if _looks_like_name(line):
            full_name = line
            break

        email_in_line = _EMAIL_PATTERN.search(line)
        if email_in_line:
            prefix = line[: email_in_line.start()].strip(" |")
            if _looks_like_name(prefix):
                full_name = prefix
                break

    return {
        "full_name": full_name,
        "email": email_match.group(0) if email_match else "",
        "phone": phone_match.group(0).strip() if phone_match else "",
        "location": location_match.group(0).strip() if location_match else "",
        "links": links,
    }


def _evidence(field: str, source_text: str, note: str):
    return {
        "field": field,
        "source_text": source_text[:800],
        "note": note,
    }


class DeterministicResumeExtractor(BaseResumeExtractor):
    provider_key = "deterministic"
    provider_label = "Deterministic local resume parser"
    provider_version = PARSER_VERSION
    extraction_mode = "deterministic"

    def extract(self, request: ResumeExtractionRequest):
        sections = _sectionize(request.document_text)
        identity = _header_values(sections["header"])

        summary = "\n".join(
            line for line in sections["summary"] if line is not None
        ).strip()
        education = _generic_entries(sections["education"])
        experience = _generic_entries(sections["experience"])
        projects = _generic_entries(sections["projects"])
        skills = _extract_skills(sections["skills"])
        certifications = _generic_entries(sections["certifications"])
        leadership = _generic_entries(sections["leadership"])

        evidence = []
        if identity["full_name"]:
            evidence.append(
                _evidence(
                    "identity.full_name",
                    identity["full_name"],
                    "Used the first reliable non-contact header line as the name candidate.",
                )
            )
        if identity["email"]:
            evidence.append(
                _evidence(
                    "identity.email",
                    identity["email"],
                    "Detected an email pattern in the resume header.",
                )
            )
        if education:
            evidence.append(
                _evidence(
                    "profile.education",
                    education[0]["source_text"],
                    "Detected content below an education heading.",
                )
            )
        if experience:
            evidence.append(
                _evidence(
                    "profile.experience",
                    experience[0]["source_text"],
                    "Detected content below an experience heading.",
                )
            )
        if projects:
            evidence.append(
                _evidence(
                    "profile.projects",
                    projects[0]["source_text"],
                    "Detected content below a projects heading.",
                )
            )
        if skills:
            evidence.append(
                _evidence(
                    "profile.skills",
                    ", ".join(skills[:20]),
                    "Split the visible skills section into reviewable skill candidates.",
                )
            )

        warnings = [
            "This deterministic baseline relies on visible section headings and does not infer missing claims."
        ]
        if not identity["full_name"]:
            warnings.append("No reliable name candidate was found in the resume header.")
        if not education:
            warnings.append("No education section was detected.")
        if not experience:
            warnings.append("No experience section was detected.")
        if not projects:
            warnings.append("No projects section was detected.")
        if not skills:
            warnings.append("No skills section was detected.")

        return self.result(
            identity=identity,
            profile={
                "professional_summary": summary,
                "education": education,
                "experience": experience,
                "projects": projects,
                "skills": skills,
                "certifications": certifications,
                "leadership": leadership,
            },
            evidence=evidence,
            warnings=warnings,
        )
