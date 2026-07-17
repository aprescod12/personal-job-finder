from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import ipaddress
import socket
import ssl
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
)

import certifi


class PageRetrievalError(RuntimeError):
    """Base error for controlled employer-page retrieval."""


class UnsafeRetrievalTarget(PageRetrievalError):
    """Raised when a URL could reach a local or otherwise non-public address."""


class RetrievalNetworkError(PageRetrievalError):
    """Raised when a public employer page cannot be reached safely."""


class RetrievalTlsError(RetrievalNetworkError):
    """Raised when a public HTTPS page cannot be verified securely."""


class RetrievalRedirectError(PageRetrievalError):
    """Raised when redirect handling is invalid or exceeds the configured limit."""


class RetrievalResponseTooLarge(PageRetrievalError):
    """Raised before an oversized response can be stored in the verification run."""


@dataclass(frozen=True)
class RetrievalPolicy:
    timeout_seconds: float = 8.0
    max_redirects: int = 5
    max_response_bytes: int = 750_000
    allowed_content_types: tuple[str, ...] = (
        "text/html",
        "application/xhtml+xml",
        "text/plain",
    )
    user_agent: str = "AmirisJobFinder/3.3 controlled-verification"


@dataclass(frozen=True)
class RetrievedPage:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str = ""
    charset: str = ""
    content_encoding: str = ""
    bytes_read: int = 0
    content_length_header: int | None = None
    body_sha256: str = ""
    body_text: str = ""
    body_stored: bool = False
    redirect_chain: list[dict[str, Any]] = field(default_factory=list)
    response_headers: dict[str, str] = field(default_factory=dict)


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _verified_https_context() -> ssl.SSLContext:
    """Build a verified TLS context with a portable CA bundle.

    Browser trust stores and Python trust stores are not always configured the same
    way on macOS. Using certifi keeps certificate verification enabled while making
    local development consistent with CI and deployed environments.
    """

    context = ssl.create_default_context(cafile=certifi.where())
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    return context


def _default_opener():
    return build_opener(
        ProxyHandler({}),
        HTTPSHandler(context=_verified_https_context()),
        _NoRedirectHandler(),
    )


def _header_text(headers, name: str) -> str:
    """Return one HTTP header as safe text.

    Some real employer servers expose blank headers as ``None`` even when a mapping
    default is supplied. Coercing here prevents transport evidence collection from
    failing after an otherwise successful request.
    """

    return str(headers.get(name) or "").strip()


class ControlledHttpRetriever:
    """Retrieve one public HTTP(S) page under strict, auditable limits.

    The retriever follows redirects itself so every destination can be validated
    before another request is sent. It never interprets whether a job is open,
    closed, or applicable; it only records transport-level evidence and a bounded
    text response for the later interpretation step.
    """

    REDIRECT_CODES = {301, 302, 303, 307, 308}

    def __init__(
        self,
        *,
        policy: RetrievalPolicy | None = None,
        opener=None,
        resolver: Callable[..., Any] | None = None,
    ):
        self.policy = policy or RetrievalPolicy()
        self.opener = opener or _default_opener()
        self.resolver = resolver or socket.getaddrinfo

    def retrieve(self, raw_url: str) -> RetrievedPage:
        requested_url = self._validate_public_url(raw_url)
        current_url = requested_url
        redirect_chain: list[dict[str, Any]] = []

        while True:
            response = self._open(current_url)
            status_code = self._status_code(response)

            if status_code in self.REDIRECT_CODES:
                location = _header_text(response.headers, "Location")
                response.close()
                if not location:
                    raise RetrievalRedirectError(
                        f"HTTP {status_code} did not include a redirect destination."
                    )
                if len(redirect_chain) >= self.policy.max_redirects:
                    raise RetrievalRedirectError(
                        f"The employer page exceeded the {self.policy.max_redirects}-redirect limit."
                    )

                next_url = urljoin(current_url, location)
                next_url = self._validate_public_url(next_url)
                redirect_chain.append(
                    {
                        "from_url": current_url,
                        "status_code": status_code,
                        "to_url": next_url,
                    }
                )
                current_url = next_url
                continue

            try:
                final_url = self._validate_public_url(
                    response.geturl() or current_url
                )
                return self._consume_response(
                    response,
                    requested_url=requested_url,
                    final_url=final_url,
                    status_code=status_code,
                    redirect_chain=redirect_chain,
                )
            finally:
                response.close()

    def _open(self, url: str):
        request = Request(
            url,
            method="GET",
            headers={
                "User-Agent": self.policy.user_agent,
                "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.1",
                "Accept-Encoding": "identity",
                "Connection": "close",
            },
        )
        try:
            return self.opener.open(
                request,
                timeout=self.policy.timeout_seconds,
            )
        except HTTPError as exc:
            # urllib represents both blocked redirects and final HTTP errors as
            # HTTPError objects. They are still response objects with headers,
            # status, URL, and a bounded body that can be audited.
            return exc
        except socket.timeout as exc:
            raise RetrievalNetworkError(
                f"The employer page timed out after {self.policy.timeout_seconds:g} seconds."
            ) from exc
        except ssl.SSLCertVerificationError as exc:
            raise RetrievalTlsError(
                "HTTPS certificate verification failed. Install the project requirements "
                "again so the trusted certificate bundle is available."
            ) from exc
        except URLError as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, ssl.SSLCertVerificationError) or (
                isinstance(reason, ssl.SSLError)
                and "CERTIFICATE_VERIFY_FAILED" in str(reason)
            ):
                raise RetrievalTlsError(
                    "HTTPS certificate verification failed. Install the project requirements "
                    "again so the trusted certificate bundle is available."
                ) from exc
            raise RetrievalNetworkError(
                f"The employer page could not be reached: {str(reason)[:300]}"
            ) from exc
        except ssl.SSLError as exc:
            raise RetrievalTlsError(
                f"The employer page could not establish a verified HTTPS connection: {str(exc)[:300]}"
            ) from exc
        except OSError as exc:
            raise RetrievalNetworkError(
                f"The employer page could not be reached: {str(exc)[:300]}"
            ) from exc

    def _validate_public_url(self, raw_url: str) -> str:
        value = (raw_url or "").strip()
        if not value:
            raise PageRetrievalError(
                "Add a direct employer job URL before running verification."
            )

        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise PageRetrievalError(
                "The saved job URL must be a complete http or https address."
            )
        if parsed.username or parsed.password:
            raise UnsafeRetrievalTarget(
                "Employer-page URLs containing embedded credentials are not allowed."
            )

        try:
            port = parsed.port
        except ValueError as exc:
            raise PageRetrievalError("The saved job URL contains an invalid port.") from exc

        expected_port = 443 if parsed.scheme == "https" else 80
        if port not in {None, expected_port}:
            raise UnsafeRetrievalTarget(
                "Only standard HTTP and HTTPS ports are allowed for verification."
            )

        hostname = parsed.hostname.rstrip(".").casefold()
        if hostname == "localhost" or hostname.endswith(".localhost"):
            raise UnsafeRetrievalTarget(
                "Localhost addresses cannot be used for employer-page verification."
            )

        try:
            address_info = self.resolver(
                hostname,
                port or expected_port,
                type=socket.SOCK_STREAM,
            )
        except (socket.gaierror, OSError) as exc:
            raise RetrievalNetworkError(
                f"The employer-page host could not be resolved: {hostname}"
            ) from exc

        addresses = set()
        for item in address_info:
            sockaddr = item[4]
            if not sockaddr:
                continue
            raw_address = str(sockaddr[0]).split("%", 1)[0]
            try:
                addresses.add(ipaddress.ip_address(raw_address))
            except ValueError as exc:
                raise UnsafeRetrievalTarget(
                    "The employer-page host resolved to an invalid address."
                ) from exc

        if not addresses:
            raise RetrievalNetworkError(
                f"The employer-page host did not resolve to an address: {hostname}"
            )
        if any(not address.is_global for address in addresses):
            raise UnsafeRetrievalTarget(
                "The employer-page host resolved to a private, local, reserved, or non-public address."
            )

        # Fragments are never sent to a server and do not belong in the audit URL.
        normalized = parsed._replace(fragment="", netloc=parsed.netloc)
        return urlunparse(normalized)

    def _consume_response(
        self,
        response,
        *,
        requested_url: str,
        final_url: str,
        status_code: int,
        redirect_chain: list[dict[str, Any]],
    ) -> RetrievedPage:
        headers = response.headers
        raw_content_type = _header_text(headers, "Content-Type")
        content_type = raw_content_type.split(";", 1)[0].strip().casefold()
        charset = ""
        if hasattr(headers, "get_content_charset"):
            charset = headers.get_content_charset() or ""
        content_encoding = _header_text(headers, "Content-Encoding").casefold()
        content_length_header = self._content_length(headers.get("Content-Length"))

        if (
            content_length_header is not None
            and content_length_header > self.policy.max_response_bytes
        ):
            raise RetrievalResponseTooLarge(
                f"The employer page declared {content_length_header:,} bytes, above the "
                f"{self.policy.max_response_bytes:,}-byte verification limit."
            )

        supported_type = content_type in self.policy.allowed_content_types
        supported_encoding = content_encoding in {"", "identity"}
        body = b""
        body_text = ""
        body_hash = ""
        body_stored = False

        if supported_type and supported_encoding:
            try:
                body = response.read(self.policy.max_response_bytes + 1)
            except socket.timeout as exc:
                raise RetrievalNetworkError(
                    "The employer page timed out while reading its response."
                ) from exc
            except OSError as exc:
                raise RetrievalNetworkError(
                    f"The employer page response could not be read: {str(exc)[:300]}"
                ) from exc

            if len(body) > self.policy.max_response_bytes:
                raise RetrievalResponseTooLarge(
                    f"The employer page exceeded the {self.policy.max_response_bytes:,}-byte verification limit."
                )

            body_hash = sha256(body).hexdigest()
            selected_charset = charset or "utf-8"
            try:
                body_text = body.decode(selected_charset, errors="replace")
            except LookupError:
                selected_charset = "utf-8"
                body_text = body.decode(selected_charset, errors="replace")
            charset = selected_charset
            body_text = body_text.replace("\x00", "")
            body_stored = True

        response_headers = {
            "content_type": raw_content_type,
            "content_encoding": content_encoding,
            "content_language": _header_text(headers, "Content-Language")[:200],
            "server": _header_text(headers, "Server")[:200],
        }

        return RetrievedPage(
            requested_url=requested_url,
            final_url=final_url,
            status_code=status_code,
            content_type=content_type,
            charset=charset,
            content_encoding=content_encoding,
            bytes_read=len(body),
            content_length_header=content_length_header,
            body_sha256=body_hash,
            body_text=body_text,
            body_stored=body_stored,
            redirect_chain=list(redirect_chain),
            response_headers=response_headers,
        )

    @staticmethod
    def _status_code(response) -> int:
        status = getattr(response, "status", None)
        if status is None:
            status = response.getcode()
        return int(status)

    @staticmethod
    def _content_length(raw_value: str | None) -> int | None:
        if not raw_value:
            return None
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            return None
        return value if value >= 0 else None
