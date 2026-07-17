from email.message import Message
from io import BytesIO
import socket
import ssl
from urllib.error import URLError
from urllib.request import HTTPSHandler

from django.test import SimpleTestCase

from .services.page_retrieval import (
    ControlledHttpRetriever,
    RetrievalNetworkError,
    RetrievalPolicy,
    RetrievalResponseTooLarge,
    RetrievalTlsError,
    UnsafeRetrievalTarget,
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


class FakeResponse:
    def __init__(self, url, *, status=200, body=b"", headers=None):
        self._url = url
        self.status = status
        self._body = BytesIO(body)
        self.headers = Message()
        for key, value in (headers or {}).items():
            self.headers[key] = value
        self.closed = False

    def read(self, size=-1):
        return self._body.read(size)

    def geturl(self):
        return self._url

    def getcode(self):
        return self.status

    def close(self):
        self.closed = True


class FakeOpener:
    def __init__(self, *responses, error=None):
        self.responses = list(responses)
        self.error = error
        self.requests = []

    def open(self, request, timeout=None):
        self.requests.append((request.full_url, timeout, dict(request.header_items())))
        if self.error:
            raise self.error
        if not self.responses:
            raise AssertionError("No fake response remains for this request.")
        return self.responses.pop(0)


class ControlledHttpRetrieverTests(SimpleTestCase):
    def test_default_opener_uses_verified_ca_bundle(self):
        retriever = ControlledHttpRetriever()
        https_handlers = [
            handler
            for handler in retriever.opener.handlers
            if isinstance(handler, HTTPSHandler)
        ]

        self.assertEqual(len(https_handlers), 1)
        context = https_handlers[0]._context
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertGreater(context.cert_store_stats()["x509_ca"], 0)

    def test_successful_html_retrieval_records_bounded_text_and_hash(self):
        body = b"<html><title>Test Engineer</title></html>"
        opener = FakeOpener(
            FakeResponse(
                "https://careers.example.com/jobs/123",
                body=body,
                headers={
                    "Content-Type": "text/html; charset=utf-8",
                    "Content-Length": str(len(body)),
                },
            )
        )
        retriever = ControlledHttpRetriever(
            opener=opener,
            resolver=public_resolver,
        )

        page = retriever.retrieve("https://careers.example.com/jobs/123#apply")

        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.final_url, "https://careers.example.com/jobs/123")
        self.assertEqual(page.content_type, "text/html")
        self.assertEqual(page.charset, "utf-8")
        self.assertEqual(page.body_text, body.decode())
        self.assertEqual(page.bytes_read, len(body))
        self.assertTrue(page.body_stored)
        self.assertEqual(len(page.body_sha256), 64)
        self.assertEqual(opener.requests[0][1], 8.0)
        self.assertEqual(opener.requests[0][0], "https://careers.example.com/jobs/123")

    def test_redirects_are_followed_and_recorded(self):
        opener = FakeOpener(
            FakeResponse(
                "https://jobs.example.com/role",
                status=302,
                headers={"Location": "https://careers.example.com/jobs/123"},
            ),
            FakeResponse(
                "https://careers.example.com/jobs/123",
                body=b"role page",
                headers={"Content-Type": "text/plain"},
            ),
        )
        retriever = ControlledHttpRetriever(
            opener=opener,
            resolver=public_resolver,
        )

        page = retriever.retrieve("https://jobs.example.com/role")

        self.assertEqual(page.final_url, "https://careers.example.com/jobs/123")
        self.assertEqual(len(page.redirect_chain), 1)
        self.assertEqual(page.redirect_chain[0]["status_code"], 302)
        self.assertEqual(len(opener.requests), 2)

    def test_private_initial_target_is_blocked_before_request(self):
        opener = FakeOpener()

        def private_resolver(host, port, **kwargs):
            return [
                (
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                    6,
                    "",
                    ("127.0.0.1", port),
                )
            ]

        retriever = ControlledHttpRetriever(
            opener=opener,
            resolver=private_resolver,
        )

        with self.assertRaises(UnsafeRetrievalTarget):
            retriever.retrieve("http://internal.example/jobs/123")

        self.assertEqual(opener.requests, [])

    def test_redirect_to_private_target_is_blocked(self):
        opener = FakeOpener(
            FakeResponse(
                "https://jobs.example.com/role",
                status=302,
                headers={"Location": "http://private.example/role"},
            )
        )

        def mixed_resolver(host, port, **kwargs):
            address = "10.0.0.5" if host == "private.example" else PUBLIC_ADDRESS
            return [
                (
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                    6,
                    "",
                    (address, port),
                )
            ]

        retriever = ControlledHttpRetriever(
            opener=opener,
            resolver=mixed_resolver,
        )

        with self.assertRaises(UnsafeRetrievalTarget):
            retriever.retrieve("https://jobs.example.com/role")

        self.assertEqual(len(opener.requests), 1)

    def test_declared_oversized_response_is_rejected(self):
        policy = RetrievalPolicy(max_response_bytes=10)
        opener = FakeOpener(
            FakeResponse(
                "https://careers.example.com/jobs/123",
                body=b"small",
                headers={
                    "Content-Type": "text/html",
                    "Content-Length": "11",
                },
            )
        )
        retriever = ControlledHttpRetriever(
            policy=policy,
            opener=opener,
            resolver=public_resolver,
        )

        with self.assertRaises(RetrievalResponseTooLarge):
            retriever.retrieve("https://careers.example.com/jobs/123")

    def test_streamed_oversized_response_is_rejected(self):
        policy = RetrievalPolicy(max_response_bytes=10)
        opener = FakeOpener(
            FakeResponse(
                "https://careers.example.com/jobs/123",
                body=b"12345678901",
                headers={"Content-Type": "text/html"},
            )
        )
        retriever = ControlledHttpRetriever(
            policy=policy,
            opener=opener,
            resolver=public_resolver,
        )

        with self.assertRaises(RetrievalResponseTooLarge):
            retriever.retrieve("https://careers.example.com/jobs/123")

    def test_unsupported_binary_content_is_not_stored(self):
        opener = FakeOpener(
            FakeResponse(
                "https://careers.example.com/jobs/123.pdf",
                body=b"%PDF-binary-data",
                headers={"Content-Type": "application/pdf"},
            )
        )
        retriever = ControlledHttpRetriever(
            opener=opener,
            resolver=public_resolver,
        )

        page = retriever.retrieve("https://careers.example.com/jobs/123.pdf")

        self.assertEqual(page.content_type, "application/pdf")
        self.assertFalse(page.body_stored)
        self.assertEqual(page.bytes_read, 0)
        self.assertEqual(page.body_text, "")

    def test_network_failure_is_normalized(self):
        opener = FakeOpener(error=URLError("connection refused"))
        retriever = ControlledHttpRetriever(
            opener=opener,
            resolver=public_resolver,
        )

        with self.assertRaises(RetrievalNetworkError) as error:
            retriever.retrieve("https://careers.example.com/jobs/123")

        self.assertIn("could not be reached", str(error.exception))

    def test_certificate_failure_is_reported_with_install_guidance(self):
        certificate_error = ssl.SSLCertVerificationError(
            1,
            "certificate verify failed",
        )
        opener = FakeOpener(error=URLError(certificate_error))
        retriever = ControlledHttpRetriever(
            opener=opener,
            resolver=public_resolver,
        )

        with self.assertRaises(RetrievalTlsError) as error:
            retriever.retrieve("https://careers.example.com/jobs/123")

        self.assertIn("Install the project requirements again", str(error.exception))
