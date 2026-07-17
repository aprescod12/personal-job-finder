"""Controlled, local semantic similarity for career evidence.

This module deliberately avoids an external API, downloaded model, or hidden prompt.
It combines normalized technical tokens with a small set of version-controlled
engineering concept families. A semantic result is only returned when there is
strong lexical evidence or a shared domain family, and its strength is capped so
it can never be treated as a direct qualification.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from .matching import normalize_text


SEMANTIC_MATCH_THRESHOLD = 0.48
SEMANTIC_STRENGTH_CAP = 0.65

STOP_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "work",
    "working",
    "support",
    "engineering",
    "engineer",
    "system",
    "systems",
    "product",
    "products",
}

# Families are broader than aliases. They connect phrases that describe the same
# engineering activity without claiming that the phrases are interchangeable.
SEMANTIC_FAMILIES = {
    "biosignal_instrumentation": {
        "label": "Biosignal and instrumentation",
        "phrases": (
            "physiological sensor",
            "physiological monitoring",
            "biomedical sensing",
            "sensor monitoring",
            "signal acquisition",
            "data acquisition",
            "diagnostic instrumentation",
            "medical instrumentation",
            "transducer",
            "biosignal",
            "patient monitoring",
        ),
    },
    "verification_test": {
        "label": "Verification and engineering test",
        "phrases": (
            "bench evaluation",
            "bench testing",
            "design verification",
            "performance testing",
            "product characterization",
            "test protocol",
            "qualification testing",
            "verification testing",
            "validation testing",
            "engineering test",
        ),
    },
    "software_test_automation": {
        "label": "Software test and automation",
        "phrases": (
            "automated tests",
            "automated testing",
            "test automation",
            "unit testing",
            "integration testing",
            "regression testing",
            "validation scripts",
            "continuous integration",
            "software verification",
            "software validation",
        ),
    },
    "embedded_controls": {
        "label": "Embedded software and controls",
        "phrases": (
            "microcontroller",
            "embedded software",
            "embedded systems",
            "firmware",
            "real time software",
            "rtos",
            "device driver",
            "hardware software integration",
            "control algorithm",
            "motor control",
            "sensor integration",
        ),
    },
    "regulated_development": {
        "label": "Regulated product development",
        "phrases": (
            "design history file",
            "design controls",
            "requirements traceability",
            "risk management",
            "quality system",
            "regulated development",
            "medical device documentation",
            "capa",
            "nonconformance",
            "verification documentation",
        ),
    },
    "systems_requirements": {
        "label": "Systems and requirements",
        "phrases": (
            "system architecture",
            "requirements analysis",
            "requirements management",
            "requirements documentation",
            "interface definition",
            "system integration",
            "traceability matrix",
            "technical specifications",
            "cross functional integration",
        ),
    },
    "backend_data_application": {
        "label": "Backend and data-backed applications",
        "phrases": (
            "django application",
            "web application",
            "database backed application",
            "backend development",
            "rest api",
            "relational database",
            "data model",
            "server side development",
            "application programming",
        ),
    },
    "manufacturing_process": {
        "label": "Manufacturing and process engineering",
        "phrases": (
            "process development",
            "manufacturing line",
            "production equipment",
            "fixture design",
            "process validation",
            "iq oq pq",
            "production troubleshooting",
            "new product introduction",
            "design transfer",
        ),
    },
    "quality_reliability": {
        "label": "Quality and reliability",
        "phrases": (
            "root cause analysis",
            "failure analysis",
            "reliability testing",
            "corrective action",
            "preventive action",
            "quality assurance",
            "design assurance",
            "supplier quality",
            "risk analysis",
        ),
    },
}


@dataclass(frozen=True)
class SemanticSimilarity:
    evidence: str
    strength: float
    similarity: float
    family_labels: tuple[str, ...]

    @property
    def explanation(self):
        families = ", ".join(self.family_labels)
        if families:
            return (
                f"Controlled semantic similarity ({self.similarity:.2f}) via "
                f"{families}"
            )
        return f"Controlled semantic similarity ({self.similarity:.2f})"


def _stem(token):
    # Small, deterministic stemmer for technical prose. It intentionally avoids
    # aggressive stemming that could create false equivalence.
    for suffix in ("ization", "ation", "ments", "ment", "ingly", "ing", "ers", "er", "ed", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


def _tokens(value):
    normalized = normalize_text(value)
    return [
        _stem(token)
        for token in normalized.split()
        if len(token) > 2 and token not in STOP_WORDS
    ]


def _phrase_present(normalized_text, phrase):
    phrase_normalized = normalize_text(phrase)
    if not phrase_normalized:
        return False
    return bool(
        re.search(
            rf"(?<![a-z0-9]){re.escape(phrase_normalized)}(?![a-z0-9])",
            normalized_text,
        )
    )


def semantic_families(value):
    normalized = normalize_text(value)
    found = set()
    for key, details in SEMANTIC_FAMILIES.items():
        if any(_phrase_present(normalized, phrase) for phrase in details["phrases"]):
            found.add(key)
    return found


def _feature_vector(value):
    tokens = _tokens(value)
    vector = Counter()

    for token in tokens:
        vector[f"token:{token}"] += 1.0

    for left, right in zip(tokens, tokens[1:]):
        vector[f"bigram:{left}_{right}"] += 0.65

    for family in semantic_families(value):
        vector[f"family:{family}"] += 3.0

    return vector


def _cosine(left, right):
    if not left or not right:
        return 0.0
    dot = sum(value * right.get(key, 0.0) for key, value in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def compare_semantically(requirement, evidence):
    requirement_families = semantic_families(requirement)
    evidence_families = semantic_families(evidence)
    shared_families = requirement_families & evidence_families
    similarity = _cosine(
        _feature_vector(requirement),
        _feature_vector(evidence),
    )

    # A family bridge permits paraphrases. Without one, lexical similarity must
    # be considerably stronger to avoid generic engineering text matching.
    if shared_families:
        qualifies = similarity >= SEMANTIC_MATCH_THRESHOLD
    else:
        qualifies = similarity >= 0.62

    if not qualifies:
        return None

    strength = min(
        SEMANTIC_STRENGTH_CAP,
        0.34 + (0.42 * similarity),
    )
    labels = tuple(
        sorted(SEMANTIC_FAMILIES[key]["label"] for key in shared_families)
    )
    return SemanticSimilarity(
        evidence=evidence,
        strength=strength,
        similarity=similarity,
        family_labels=labels,
    )


def best_semantic_match(requirement, evidence_items):
    best = None
    for evidence in evidence_items:
        candidate = compare_semantically(requirement, evidence)
        if candidate and (best is None or candidate.strength > best.strength):
            best = candidate
    return best


__all__ = (
    "SEMANTIC_FAMILIES",
    "SEMANTIC_MATCH_THRESHOLD",
    "SEMANTIC_STRENGTH_CAP",
    "SemanticSimilarity",
    "best_semantic_match",
    "compare_semantically",
    "semantic_families",
)
