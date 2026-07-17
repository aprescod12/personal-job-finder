from io import BytesIO
import socket

from django.test import SimpleTestCase

from .services.page_retrieval import (
    ControlledHttpRetriever,
    RetrievalRedirectError,
)


PUBLIC_ADDRESS = "93.184.216.34"


def public_resolver(host, port, **kwargs):
    return [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            (PUBLIC_ADDRESS, port),
        )
    ]


class NullableHeaders:
    """Mimic real response mappings that return None for blank headers."""

    def __init__(self, values=None):
        self.values = values or {}

    def get(self, name, default=None):
        return self.values.get(name)

    def get_content_charset(self):
        return None


class FakeResponse:
    def __init__(self, url, *, status=200, body=b"", headers=None):
        self._url = url
        self.status = status
        self._body = BytesIO(body)
        self.headers = headers or NullableHeaders()

    def read(self, size=-1):
        return self._body.read(size)

    def geturl(self):
        return self._url

    def getcode(self):
        return self.status

    def close(self):
        pass


class FakeOpener:
    def __init__(self, response):
        self.response = response

    def open(self, request, timeout=None):
        return self.response


class NullableResponseHeaderTests(SimpleTestCase):
    def test_missing_optional_headers_do_not_fail_retrieval(self):
        url = "https://careers.example.com/jobs/123"
        response = FakeResponse(url, body=b"employer response without headers")
        retriever = ControlledHttpRetriever(
            opener=FakeOpener(response),
            resolver=public_resolver,
        )

        page = retriever.retrieve(url)

        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.final_url, url)
        self.assertEqual(page.content_type, "")
        self.assertEqual(page.content_encoding, "")
        self.assertEqual(page.response_headers["content_language"], "")
        self.assertEqual(page.response_headers["server"], "")
        self.assertFalse(page.body_stored)

    def test_missing_redirect_location_raises_domain_error_not_attribute_error(self):
        url = "https://careers.example.com/jobs/123"
        response = FakeResponse(url, status=302)
        retriever = ControlledHttpRetriever(
            opener=FakeOpener(response),
            resolver=public_resolver,
        )

        with self.assertRaises(RetrievalRedirectError) as error:
            retriever.retrieve(url)

        self.assertIn("did not include a redirect destination", str(error.exception))
