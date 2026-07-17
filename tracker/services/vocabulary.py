"""Version-controlled vocabulary for transparent, deterministic matching.

The vocabulary is deliberately explicit and reviewable. It normalizes common
abbreviations and buzzwords without relying on an LLM or hidden prompt.
"""

CONCEPTS = {
    "verification_validation": {
        "label": "Verification and validation",
        "aliases": (
            "v&v",
            "v and v",
            "verification and validation",
            "design verification",
            "product verification",
            "validation testing",
            "testing and validation",
            "test and validation",
            "technical testing",
        ),
    },
    "test_engineering": {
        "label": "Test engineering",
        "aliases": (
            "test engineering",
            "test engineer",
            "testing",
            "test planning",
            "test execution",
            "test protocol",
            "test protocols",
            "test protocol development",
            "system testing",
            "product testing",
        ),
    },
    "requirements_engineering": {
        "label": "Requirements engineering",
        "aliases": (
            "requirements engineering",
            "requirements documentation",
            "requirements management",
            "requirements traceability",
            "traceability matrix",
            "requirements analysis",
        ),
    },
    "systems_engineering": {
        "label": "Systems engineering",
        "aliases": (
            "systems engineering",
            "systems engineer",
            "system engineering",
            "systems integration",
            "system integration",
            "system architecture",
        ),
    },
    "quality_engineering": {
        "label": "Quality engineering",
        "aliases": (
            "quality engineering",
            "quality engineer",
            "quality assurance",
            "design assurance",
            "quality systems",
            "capa",
            "root cause analysis",
        ),
    },
    "embedded_systems": {
        "label": "Embedded systems",
        "aliases": (
            "embedded systems",
            "embedded software",
            "firmware",
            "embedded c",
            "microcontroller programming",
            "hardware software integration",
        ),
    },
    "software_development": {
        "label": "Software development",
        "aliases": (
            "software development",
            "software engineering",
            "programming",
            "application development",
            "coding",
        ),
    },
    "python": {"label": "Python", "aliases": ("python",)},
    "django": {"label": "Django", "aliases": ("django",)},
    "matlab": {"label": "MATLAB", "aliases": ("matlab",)},
    "c_programming": {
        "label": "C/C++ programming",
        "aliases": ("c programming", "c++", "cpp", "embedded c"),
    },
    "data_analysis": {
        "label": "Data analysis",
        "aliases": (
            "data analysis",
            "data analytics",
            "analyze data",
            "statistical analysis",
        ),
    },
    "signal_processing": {
        "label": "Signal processing",
        "aliases": ("signal processing", "digital signal processing", "dsp"),
    },
    "instrumentation": {
        "label": "Biomedical/electronic instrumentation",
        "aliases": (
            "instrumentation",
            "biomedical instrumentation",
            "medical instrumentation",
            "diagnostic instrumentation",
            "electronic instrumentation",
            "sensors",
            "sensor systems",
        ),
    },
    "circuit_design": {
        "label": "Circuit and electronics design",
        "aliases": (
            "circuit design",
            "electronics design",
            "pcb design",
            "electrical design",
        ),
    },
    "electrical_engineering": {
        "label": "Electrical engineering",
        "aliases": (
            "electrical engineering",
            "electrical engineer",
            "electronics engineering",
        ),
    },
    "biomedical_engineering": {
        "label": "Biomedical engineering",
        "aliases": (
            "biomedical engineering",
            "biomedical engineer",
            "bioengineering",
        ),
    },
    "computer_science": {
        "label": "Computer science",
        "aliases": ("computer science", "computer scientist"),
    },
    "mechanical_engineering": {
        "label": "Mechanical engineering",
        "aliases": ("mechanical engineering", "mechanical engineer"),
    },
    "medical_devices": {
        "label": "Medical devices / MedTech",
        "aliases": (
            "medical device",
            "medical devices",
            "medtech",
            "medical technology",
            "healthcare technology",
            "regulated medical product",
            "diagnostic device",
        ),
    },
    "healthcare": {
        "label": "Healthcare",
        "aliases": (
            "healthcare",
            "health care",
            "clinical technology",
            "hospital technology",
        ),
    },
    "iso_13485": {"label": "ISO 13485", "aliases": ("iso 13485",)},
    "fda_design_controls": {
        "label": "FDA design controls",
        "aliases": (
            "fda design controls",
            "design controls",
            "21 cfr 820",
            "qsr",
        ),
    },
    "regulated_product_development": {
        "label": "Regulated product development",
        "aliases": (
            "regulated product development",
            "regulated environment",
            "regulated industry",
            "medical device regulations",
        ),
    },
    "role_biomedical": {
        "label": "Biomedical engineering roles",
        "aliases": (
            "biomedical engineer",
            "biomedical engineering",
            "bioengineer",
        ),
    },
    "role_medical_device": {
        "label": "Medical-device engineering roles",
        "aliases": (
            "medical device engineer",
            "medical devices engineer",
            "product engineer medical device",
        ),
    },
    "role_systems": {
        "label": "Systems engineering roles",
        "aliases": (
            "systems engineer",
            "systems engineering",
            "system engineer",
        ),
    },
    "role_test": {
        "label": "Test engineering roles",
        "aliases": (
            "test engineer",
            "test engineering",
            "systems test engineer",
            "software test engineer",
            "manufacturing test engineer",
        ),
    },
    "role_validation": {
        "label": "Validation / V&V roles",
        "aliases": (
            "validation engineer",
            "verification engineer",
            "v&v engineer",
            "verification and validation engineer",
        ),
    },
    "role_quality": {
        "label": "Quality / design-assurance roles",
        "aliases": (
            "quality engineer",
            "quality engineering",
            "design assurance engineer",
        ),
    },
    "role_software": {
        "label": "Software engineering roles",
        "aliases": (
            "software engineer",
            "software developer",
            "medical device software engineer",
        ),
    },
    "role_clinical": {
        "label": "Clinical engineering roles",
        "aliases": ("clinical engineer", "clinical engineering"),
    },
    "role_applications": {
        "label": "Applications engineering roles",
        "aliases": (
            "applications engineer",
            "application engineer",
            "field applications engineer",
        ),
    },
    "role_reliability": {
        "label": "Reliability engineering roles",
        "aliases": ("reliability engineer", "reliability engineering"),
    },
    "role_field_service": {
        "label": "Field-service engineering roles",
        "aliases": (
            "field service engineer",
            "service engineer",
            "biomedical equipment technician",
        ),
    },
}

RELATED_CONCEPTS = {
    "verification_validation": {
        "test_engineering": 0.80,
        "requirements_engineering": 0.65,
        "quality_engineering": 0.60,
    },
    "test_engineering": {
        "verification_validation": 0.80,
        "quality_engineering": 0.55,
        "systems_engineering": 0.55,
    },
    "requirements_engineering": {
        "systems_engineering": 0.75,
        "verification_validation": 0.65,
    },
    "systems_engineering": {
        "requirements_engineering": 0.75,
        "test_engineering": 0.55,
    },
    "quality_engineering": {
        "verification_validation": 0.60,
        "test_engineering": 0.55,
        "regulated_product_development": 0.60,
    },
    "embedded_systems": {
        "software_development": 0.65,
        "c_programming": 0.75,
        "circuit_design": 0.55,
    },
    "software_development": {
        "python": 0.55,
        "django": 0.55,
        "embedded_systems": 0.55,
    },
    "instrumentation": {
        "biomedical_engineering": 0.70,
        "electrical_engineering": 0.65,
        "circuit_design": 0.60,
    },
    "medical_devices": {
        "healthcare": 0.70,
        "biomedical_engineering": 0.75,
        "regulated_product_development": 0.70,
    },
    "healthcare": {
        "medical_devices": 0.70,
        "biomedical_engineering": 0.60,
    },
    "electrical_engineering": {
        "biomedical_engineering": 0.55,
        "computer_science": 0.35,
        "mechanical_engineering": 0.35,
    },
    "biomedical_engineering": {
        "electrical_engineering": 0.55,
        "medical_devices": 0.75,
        "healthcare": 0.60,
    },
    "iso_13485": {
        "regulated_product_development": 0.70,
        "fda_design_controls": 0.55,
    },
    "fda_design_controls": {
        "regulated_product_development": 0.75,
        "iso_13485": 0.55,
    },
}

ROLE_RELATIONSHIPS = {
    "role_biomedical": {
        "role_medical_device": 0.85,
        "role_systems": 0.55,
        "role_clinical": 0.65,
    },
    "role_medical_device": {
        "role_biomedical": 0.85,
        "role_validation": 0.70,
        "role_quality": 0.65,
        "role_systems": 0.65,
    },
    "role_systems": {
        "role_validation": 0.70,
        "role_test": 0.65,
        "role_biomedical": 0.55,
    },
    "role_test": {
        "role_validation": 0.85,
        "role_quality": 0.60,
        "role_systems": 0.65,
        "role_reliability": 0.60,
    },
    "role_validation": {
        "role_test": 0.85,
        "role_quality": 0.70,
        "role_systems": 0.70,
        "role_medical_device": 0.70,
    },
    "role_quality": {
        "role_validation": 0.70,
        "role_test": 0.60,
        "role_medical_device": 0.65,
        "role_reliability": 0.60,
    },
    "role_software": {"role_test": 0.55, "role_systems": 0.50},
    "role_clinical": {
        "role_biomedical": 0.65,
        "role_field_service": 0.60,
        "role_applications": 0.55,
    },
    "role_applications": {
        "role_field_service": 0.65,
        "role_clinical": 0.55,
        "role_systems": 0.45,
    },
    "role_reliability": {"role_test": 0.60, "role_quality": 0.60},
    "role_field_service": {
        "role_applications": 0.65,
        "role_clinical": 0.60,
    },
}
