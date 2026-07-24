import os

import certifi
from django.apps import AppConfig


class JobDiscoveryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "job_discovery"
    verbose_name = "Job Discovery"

    def ready(self):
        # Python installations on macOS do not always expose a usable default CA
        # path to OpenSSL. Point standard-library HTTPS clients at the project's
        # maintained certifi bundle while preserving any deliberate user override.
        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
