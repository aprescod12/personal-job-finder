"""Django settings for the personal job finder."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().casefold() in {"1", "true", "yes", "on"}


def _env_positive_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return value if value > 0 else default


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "development-only-not-for-production")
DEBUG = True
ALLOWED_HOSTS = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "tracker",
    "intake_history.apps.IntakeHistoryConfig",
    "candidate_profile.apps.CandidateProfileConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Stage 4 job-intake provider. The deterministic provider remains the default.
JOB_INTAKE_EXTRACTOR = os.getenv(
    "JOB_INTAKE_EXTRACTOR",
    "tracker.services.job_intake.DeterministicJobExtractor",
).strip()

# Selecting an AI provider is insufficient on its own. This separate switch
# must also be enabled deliberately before a live model request can occur.
JOB_INTAKE_AI_ENABLED = _env_bool("JOB_INTAKE_AI_ENABLED", default=False)

# Step 3C fallback remains local and deterministic. It is disclosed visibly on
# the review page whenever the primary extractor cannot produce a safe draft.
JOB_INTAKE_FALLBACK_ENABLED = _env_bool(
    "JOB_INTAKE_FALLBACK_ENABLED",
    default=True,
)
JOB_INTAKE_FALLBACK_EXTRACTOR = os.getenv(
    "JOB_INTAKE_FALLBACK_EXTRACTOR",
    "tracker.services.job_intake.DeterministicJobExtractor",
).strip()

# Non-secret request configuration. The API key is intentionally read directly
# from the process environment by the backend only when a request is made.
OPENAI_JOB_EXTRACTION_MODEL = (
    os.getenv("OPENAI_JOB_EXTRACTION_MODEL", "gpt-5-mini").strip()
    or "gpt-5-mini"
)
OPENAI_JOB_EXTRACTION_TIMEOUT_SECONDS = _env_positive_int(
    "OPENAI_JOB_EXTRACTION_TIMEOUT_SECONDS",
    30,
)
OPENAI_JOB_EXTRACTION_MAX_OUTPUT_TOKENS = _env_positive_int(
    "OPENAI_JOB_EXTRACTION_MAX_OUTPUT_TOKENS",
    4000,
)

# Stage 5 resume extraction remains deterministic unless both the provider path
# and this separate AI safety switch are changed deliberately.
RESUME_EXTRACTOR = os.getenv(
    "RESUME_EXTRACTOR",
    "candidate_profile.services.resume_deterministic.DeterministicResumeExtractor",
).strip()
RESUME_AI_ENABLED = _env_bool("RESUME_AI_ENABLED", default=False)
RESUME_FALLBACK_ENABLED = _env_bool("RESUME_FALLBACK_ENABLED", default=True)
RESUME_FALLBACK_EXTRACTOR = os.getenv(
    "RESUME_FALLBACK_EXTRACTOR",
    "candidate_profile.services.resume_deterministic.DeterministicResumeExtractor",
).strip()

# OpenAI resume extraction sends only locally parsed text and asks the model for
# compact claims-only JSON. Exact evidence excerpts are generated locally after
# validation. One bounded retry is allowed only for an output-limit response.
OPENAI_RESUME_EXTRACTION_MODEL = (
    os.getenv("OPENAI_RESUME_EXTRACTION_MODEL", "gpt-5-mini").strip()
    or "gpt-5-mini"
)
OPENAI_RESUME_EXTRACTION_TIMEOUT_SECONDS = _env_positive_int(
    "OPENAI_RESUME_EXTRACTION_TIMEOUT_SECONDS",
    120,
)
OPENAI_RESUME_EXTRACTION_MAX_OUTPUT_TOKENS = _env_positive_int(
    "OPENAI_RESUME_EXTRACTION_MAX_OUTPUT_TOKENS",
    8000,
)
OPENAI_RESUME_EXTRACTION_RETRY_MAX_OUTPUT_TOKENS = _env_positive_int(
    "OPENAI_RESUME_EXTRACTION_RETRY_MAX_OUTPUT_TOKENS",
    12000,
)
OPENAI_RESUME_EXTRACTION_MAX_INPUT_CHARS = _env_positive_int(
    "OPENAI_RESUME_EXTRACTION_MAX_INPUT_CHARS",
    60000,
)
OPENAI_RESUME_EXTRACTION_REASONING_EFFORT = (
    os.getenv("OPENAI_RESUME_EXTRACTION_REASONING_EFFORT", "low").strip()
    or "low"
)
