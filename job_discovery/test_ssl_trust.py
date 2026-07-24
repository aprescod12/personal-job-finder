import os
from importlib import import_module
from unittest.mock import patch

from django.test import SimpleTestCase

from .apps import JobDiscoveryConfig


class DiscoverySSLTrustTests(SimpleTestCase):
    def _config(self):
        return JobDiscoveryConfig("job_discovery", import_module("job_discovery"))

    def test_ready_uses_certifi_when_no_ca_override_exists(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SSL_CERT_FILE", None)
            with patch(
                "job_discovery.apps.certifi.where",
                return_value="/tmp/certifi-ca.pem",
            ):
                self._config().ready()

            self.assertEqual(os.environ["SSL_CERT_FILE"], "/tmp/certifi-ca.pem")

    def test_ready_preserves_deliberate_ca_override(self):
        with patch.dict(
            os.environ,
            {"SSL_CERT_FILE": "/tmp/custom-ca.pem"},
            clear=False,
        ):
            with patch(
                "job_discovery.apps.certifi.where",
                return_value="/tmp/certifi-ca.pem",
            ):
                self._config().ready()

            self.assertEqual(os.environ["SSL_CERT_FILE"], "/tmp/custom-ca.pem")
