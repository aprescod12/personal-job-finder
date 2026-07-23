from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Protocol


@dataclass(frozen=True)
class DiscoveryQuery:
    target_roles: tuple[str, ...] = ()
    target_industries: tuple[str, ...] = ()
    preferred_locations: tuple[str, ...] = ()
    preferred_work_arrangement: str = ""
    preferred_employment_type: str = ""
    experience_level: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DiscoveredOpportunity:
    external_id: str
    source_url: str
    title_hint: str
    company_hint: str
    location_hint: str
    raw_listing_text: str
    employment_type_hint: str = ""
    work_arrangement_hint: str = ""
    industry_hint: str = ""
    seniority_hint: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class DiscoveryProvider(Protocol):
    key: str
    label: str
    version: str

    def discover(self, query: DiscoveryQuery) -> Iterable[DiscoveredOpportunity]: ...


class FixtureDiscoveryProvider:
    """Deterministic, offline provider used to validate the discovery workflow."""

    key = "fixture"
    label = "Local fixture provider"
    version = "fixture-discovery-v1"

    def discover(self, query: DiscoveryQuery) -> Iterable[DiscoveredOpportunity]:
        del query  # The fixture is stable; broad preference labeling happens downstream.
        return (
            DiscoveredOpportunity(
                external_id="fixture-medtech-test-engineer-001",
                source_url="https://jobs.example.com/listings/medtech-test-engineer-001",
                title_hint="Junior Medical Device Test Engineer",
                company_hint="Northstar Medical Systems",
                location_hint="Philadelphia, PA",
                employment_type_hint="Full-time",
                work_arrangement_hint="Hybrid",
                industry_hint="Medical devices",
                seniority_hint="Entry level",
                raw_listing_text=(
                    "Junior Medical Device Test Engineer\n"
                    "Northstar Medical Systems\n"
                    "Philadelphia, PA · Hybrid · Full-time\n\n"
                    "Support verification and validation testing for connected medical "
                    "devices. Execute test protocols, document results, investigate "
                    "failures, and collaborate with electrical, software, and quality "
                    "engineers.\n\n"
                    "Required qualifications:\n"
                    "- Bachelor's degree in electrical engineering, biomedical engineering, "
                    "or a related field.\n"
                    "- Familiarity with Python or MATLAB.\n"
                    "- Strong technical documentation and laboratory skills.\n\n"
                    "Preferred qualifications:\n"
                    "- Exposure to IEC 60601, design controls, or medical-device V&V."
                ),
                metadata={"fixture_group": "priority_medtech"},
            ),
            DiscoveredOpportunity(
                external_id="fixture-embedded-systems-002",
                source_url="https://jobs.example.com/listings/embedded-systems-002",
                title_hint="Embedded Systems Engineer I",
                company_hint="Harbor Biomedical Instruments",
                location_hint="Boston, MA",
                employment_type_hint="Full-time",
                work_arrangement_hint="On-site",
                industry_hint="Biomedical instrumentation",
                seniority_hint="Entry level",
                raw_listing_text=(
                    "Embedded Systems Engineer I\n"
                    "Harbor Biomedical Instruments\n"
                    "Boston, MA · On-site · Full-time\n\n"
                    "Develop and test embedded firmware for physiological sensing "
                    "instruments. Work with C, microcontrollers, serial interfaces, "
                    "sensors, and bench-test equipment. Participate in requirements, "
                    "design reviews, debugging, and verification activities.\n\n"
                    "Qualifications include a bachelor's degree in electrical engineering "
                    "or computer engineering and academic or project experience with "
                    "embedded systems."
                ),
                metadata={"fixture_group": "adjacent_biomedical"},
            ),
            DiscoveredOpportunity(
                external_id="fixture-quality-engineer-003",
                source_url="https://jobs.example.com/listings/quality-engineer-003",
                title_hint="Quality Engineer - New Product Introduction",
                company_hint="ClearPath Diagnostics",
                location_hint="New Jersey",
                employment_type_hint="Full-time",
                work_arrangement_hint="On-site",
                industry_hint="In-vitro diagnostics",
                seniority_hint="Early career",
                raw_listing_text=(
                    "Quality Engineer - New Product Introduction\n"
                    "ClearPath Diagnostics\n"
                    "New Jersey · On-site · Full-time\n\n"
                    "Support design controls, risk-management documentation, verification "
                    "planning, supplier quality, CAPA investigations, and transfer of "
                    "diagnostic products into manufacturing.\n\n"
                    "Bachelor's degree in engineering required. Internship, laboratory, "
                    "or project experience in regulated product development preferred."
                ),
                metadata={"fixture_group": "quality_medtech"},
            ),
            DiscoveredOpportunity(
                external_id="fixture-general-software-004",
                source_url="https://jobs.example.com/listings/general-software-004",
                title_hint="Software Engineer I",
                company_hint="Civic Commerce Labs",
                location_hint="Remote - United States",
                employment_type_hint="Full-time",
                work_arrangement_hint="Remote",
                industry_hint="E-commerce software",
                seniority_hint="Entry level",
                raw_listing_text=(
                    "Software Engineer I\n"
                    "Civic Commerce Labs\n"
                    "Remote - United States · Full-time\n\n"
                    "Build web services and internal applications using Python, Django, "
                    "JavaScript, and relational databases. Participate in code review, "
                    "testing, deployment, and production support.\n\n"
                    "Bachelor's degree or equivalent project experience required."
                ),
                metadata={"fixture_group": "outside_primary_industry"},
            ),
        )
