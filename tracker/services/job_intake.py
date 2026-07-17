import re
from datetime import datetime

from tracker.models import JobPosting, JobRequirement


PARSER_VERSION = "deterministic-intake-v1"

_LABEL_PATTERNS = {
    "title": ("job title", "position title", "role title", "position"),
    "company": ("company", "employer", "organization", "organisation"),
    "location": ("location", "job location", "work location"),
}

_SECTION_HEADINGS = {
    "responsibilities": {
        "responsibilities",
        "what you will do",
        "what you'll do",
        "the role",
        "your responsibilities",
        "key responsibilities",
    },
    "required_skills": {
        "requirements",
        "required qualifications",
        "qualifications",
        "what you bring",
        "minimum qualifications",
    },
    "preferred_skills": {
        "preferred qualifications",
        "preferred skills",
        "nice to have",
        "nice-to-have",
        "bonus qualifications",
    },
}

_ALL_SECTION_HEADINGS = set().union(*_SECTION_HEADINGS.values(), {
    "about us",
    "about the company",
    "benefits",
    "compensation",
    "salary",
    "equal opportunity",
    "how to apply",
    "application process",
})

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%B %d %Y",
    "%b %d %Y",
)


def _clean_line(value):
    value = re.sub(r"^[\s\-–—•*▪◦]+", "", value or "")
    return re.sub(r"\s+", " ", value).strip()


def _normalized_heading(value):
    value = _clean_line(value).casefold().rstrip(":")
    return re.sub(r"[^a-z0-9' -]+", "", value).strip()


def _lines(raw_text):
    return [_clean_line(line) for line in (raw_text or "").splitlines() if _clean_line(line)]


def _find_labeled_value(lines, labels):
    for line in lines:
        for label in labels:
            match = re.match(rf"^{re.escape(label)}\s*[:\-]\s*(.+)$", line, re.IGNORECASE)
            if match:
                return match.group(1).strip(), f"Detected from labeled field: {label}."
    return "", ""


def _first_title_candidate(lines):
    for line in lines[:6]:
        normalized = _normalized_heading(line)
        if normalized in _ALL_SECTION_HEADINGS:
            continue
        if line.lower().startswith(("http://", "https://")):
            continue
        if 3 <= len(line) <= 120:
            return line, "Used the first short non-heading line as a title hint."
    return "", ""


def _extract_section(lines, headings):
    start = None
    for index, line in enumerate(lines):
        if _normalized_heading(line) in headings:
            start = index + 1
            break
    if start is None:
        return ""

    collected = []
    for line in lines[start:]:
        if _normalized_heading(line) in _ALL_SECTION_HEADINGS:
            break
        collected.append(line)
        if len(collected) >= 20:
            break
    return "\n".join(collected).strip()


def _detect_employment_type(text):
    lowered = text.casefold()
    patterns = (
        (r"\bintern(ship)?\b", JobPosting.EmploymentType.INTERNSHIP),
        (r"\bpart[ -]?time\b", JobPosting.EmploymentType.PART_TIME),
        (r"\bcontract(or)?\b", JobPosting.EmploymentType.CONTRACT),
        (r"\btemporary\b|\btemp\b", JobPosting.EmploymentType.TEMPORARY),
        (r"\bfull[ -]?time\b", JobPosting.EmploymentType.FULL_TIME),
    )
    for pattern, value in patterns:
        if re.search(pattern, lowered):
            return value
    return JobPosting.EmploymentType.UNKNOWN


def _detect_work_arrangement(text):
    lowered = text.casefold()
    if re.search(r"\bhybrid\b", lowered):
        return JobPosting.WorkArrangement.HYBRID
    if re.search(r"\bremote\b|work from home", lowered):
        return JobPosting.WorkArrangement.REMOTE
    if re.search(r"\bon[ -]?site\b|\bin office\b", lowered):
        return JobPosting.WorkArrangement.ONSITE
    return JobPosting.WorkArrangement.UNKNOWN


def _detect_seniority(title, text):
    sample = f"{title} {text[:1200]}".casefold()
    if re.search(r"\bintern(ship)?\b|\bco-op\b", sample):
        return JobRequirement.SeniorityLevel.INTERNSHIP
    if re.search(r"\bprincipal\b|\bstaff\b|\bsenior\b|\bsr\.?\b", sample):
        return JobRequirement.SeniorityLevel.SENIOR
    if re.search(r"\blead\b|\bmanager\b|\bdirector\b", sample):
        return JobRequirement.SeniorityLevel.LEAD_MANAGER
    if re.search(r"\bentry[ -]?level\b|\bnew grad\b|\bgraduate\b", sample):
        return JobRequirement.SeniorityLevel.ENTRY_LEVEL
    if re.search(r"\bjunior\b|\bassociate\b|\bearly career\b", sample):
        return JobRequirement.SeniorityLevel.EARLY_CAREER
    return JobRequirement.SeniorityLevel.UNKNOWN


def _parse_deadline(text):
    rolling = re.search(r"open until filled|rolling applications?|applications? accepted on a rolling basis", text, re.IGNORECASE)
    if rolling:
        return JobPosting.DeadlineStatus.ROLLING, "", "Detected rolling or open-until-filled language."

    label_match = re.search(
        r"(?:application deadline|apply by|closing date|applications? close)\s*[:\-]?\s*([^\n.;]{4,40})",
        text,
        re.IGNORECASE,
    )
    if label_match:
        candidate = label_match.group(1).strip()
        for date_format in _DATE_FORMATS:
            try:
                parsed = datetime.strptime(candidate, date_format).date()
                return JobPosting.DeadlineStatus.CONFIRMED, parsed.isoformat(), f"Detected deadline from: {candidate}."
            except ValueError:
                continue
        return JobPosting.DeadlineStatus.UNKNOWN, "", f"Found deadline language but could not safely parse: {candidate}."

    if re.search(r"no application deadline|deadline not stated|no deadline", text, re.IGNORECASE):
        return JobPosting.DeadlineStatus.NOT_STATED, "", "Detected an explicit no-deadline statement."

    return JobPosting.DeadlineStatus.UNKNOWN, "", "No reliable deadline statement was detected."


def _extract_education(required_text):
    education_lines = []
    for line in required_text.splitlines():
        if re.search(r"\b(bachelor|master|ph\.?d|degree|b\.?s\.?|m\.?s\.?)\b", line, re.IGNORECASE):
            education_lines.append(line)
    return "\n".join(education_lines)


def _extract_work_authorization(lines):
    matches = []
    for line in lines:
        if re.search(r"sponsor|work authorization|authorized to work|visa|citizen|permanent resident", line, re.IGNORECASE):
            matches.append(line)
    return "\n".join(matches[:8])


def extract_job_intake(raw_text, *, source_url="", source_label=""):
    cleaned_lines = _lines(raw_text)
    evidence = []
    warnings = []

    title, note = _find_labeled_value(cleaned_lines, _LABEL_PATTERNS["title"])
    if not title:
        title, note = _first_title_candidate(cleaned_lines)
    if note:
        evidence.append(note)

    company, note = _find_labeled_value(cleaned_lines, _LABEL_PATTERNS["company"])
    if note:
        evidence.append(note)
    if not company:
        warnings.append("Company was not confidently detected; review is required.")

    location, note = _find_labeled_value(cleaned_lines, _LABEL_PATTERNS["location"])
    if note:
        evidence.append(note)
    if not location:
        for line in cleaned_lines[:12]:
            if line.casefold() in {"remote", "hybrid", "on-site", "onsite"}:
                location = line
                evidence.append("Used a standalone work-location line as the location hint.")
                break

    required_skills = _extract_section(cleaned_lines, _SECTION_HEADINGS["required_skills"])
    preferred_skills = _extract_section(cleaned_lines, _SECTION_HEADINGS["preferred_skills"])
    responsibilities = _extract_section(cleaned_lines, _SECTION_HEADINGS["responsibilities"])
    required_education = _extract_education(required_skills)
    work_authorization = _extract_work_authorization(cleaned_lines)

    deadline_status, application_deadline, deadline_note = _parse_deadline(raw_text)
    evidence.append(deadline_note)

    employment_type = _detect_employment_type(raw_text)
    work_arrangement = _detect_work_arrangement(raw_text)
    seniority_level = _detect_seniority(title, raw_text)

    if not title:
        warnings.append("Title was not confidently detected; review is required.")
    if not required_skills:
        warnings.append("No clear qualifications section was detected.")

    return {
        "parser_version": PARSER_VERSION,
        "job": {
            "title": title,
            "company": company,
            "location": location,
            "job_url": source_url,
            "source": source_label or "Pasted listing",
            "employment_type": employment_type,
            "work_arrangement": work_arrangement,
            "deadline_status": deadline_status,
            "application_deadline": application_deadline,
            "description": raw_text.strip(),
            "next_action": "Verify listing and review requirements",
        },
        "requirements": {
            "role_family": title,
            "seniority_level": seniority_level,
            "industry": "",
            "required_skills": required_skills,
            "preferred_skills": preferred_skills,
            "required_education": required_education,
            "preferred_education": "",
            "minimum_years_experience": None,
            "maximum_years_experience": None,
            "responsibilities": responsibilities,
            "certifications": "",
            "work_authorization_requirements": work_authorization,
            "hard_disqualifiers": work_authorization if re.search(r"no sponsorship|cannot sponsor|must be (?:a )?u\.?s\.? citizen", work_authorization, re.IGNORECASE) else "",
            "requirement_notes": "Review every extracted field against the original posting before relying on the match score.",
        },
        "evidence": evidence,
        "warnings": warnings,
    }
