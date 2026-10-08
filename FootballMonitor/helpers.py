"""Share safe web requests and readable match text across the program."""

import json
from json import JSONDecodeError
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from config import (
    ESPN_API_HOST,
    MAX_REPLY_SIZE_BYTES,
    REQUEST_TIMEOUT_SECONDS,
)


class FootballDataError(Exception):
    """Explain when the program cannot get usable football information."""


class StopWebsiteRedirects(HTTPRedirectHandler):
    """Stop ESPN data requests from being sent to a different website."""

    def redirect_request(
        self,
        request: Request,
        response: object,
        status_code: int,
        reason: str,
        response_headers: object,
        new_address: str,
    ) -> None:
        """Refuse a redirect so a reply cannot choose a different website."""
        del request, response, status_code, reason, response_headers, new_address
        return None


def get_espn_json(request_address: str) -> dict[str, object]:
    """Download a small JSON reply from ESPN's official data website."""
    address_parts = urlsplit(request_address)
    if (
        address_parts.scheme != "https"
        or address_parts.hostname != ESPN_API_HOST
        or address_parts.port is not None
        or address_parts.username is not None
        or address_parts.password is not None
    ):
        raise FootballDataError(
            "The program stopped a web address that is not ESPN's approved "
            "football data website."
        )

    request = Request(
        request_address,
        headers={"User-Agent": "FootballMonitor/1.0"},
    )
    safe_opener = build_opener(StopWebsiteRedirects())

    try:
        with safe_opener.open(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            content_type = response.headers.get("Content-Type", "")
            if "application/json" not in content_type.lower():
                raise FootballDataError(
                    "ESPN sent information in a format the program cannot read."
                )
            response_bytes = response.read(MAX_REPLY_SIZE_BYTES + 1)
    except HTTPError as error:
        raise FootballDataError(
            f"ESPN could not provide the information (web status {error.code}). "
            "Please try again later."
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        raise FootballDataError(
            "The program could not connect to ESPN. Check your internet "
            "connection and try again."
        ) from error

    if len(response_bytes) > MAX_REPLY_SIZE_BYTES:
        raise FootballDataError(
            "ESPN sent more information than the program can safely read."
        )

    try:
        reply = json.loads(response_bytes.decode("utf-8"))
    except (JSONDecodeError, UnicodeDecodeError) as error:
        raise FootballDataError(
            "ESPN sent information that the program could not understand."
        ) from error

    if not isinstance(reply, dict):
        raise FootballDataError(
            "ESPN sent information in an unexpected format. Please try again later."
        )
    return reply


def clean_words(value: object, fallback: str = "Not available") -> str:
    """Return useful clean words, or a clear replacement if none are given."""
    if isinstance(value, str) and value.strip():
        return " ".join(value.split())
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return fallback
