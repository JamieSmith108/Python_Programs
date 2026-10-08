"""Share safe web requests and readable match text across the program."""

import json
from json import JSONDecodeError
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

from config import (
    ESPN_API_HOST,
    ESPN_IMAGE_HOST,
    MAX_IMAGE_SIZE_BYTES,
    MAX_REPLY_SIZE_BYTES,
    REQUEST_TIMEOUT_SECONDS,
)
from logging_service import log_api_communication


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
    correlation_id = str(uuid4())
    address_parts = urlsplit(request_address)
    if (
        address_parts.scheme != "https"
        or address_parts.hostname != ESPN_API_HOST
        or address_parts.port is not None
        or address_parts.username is not None
        or address_parts.password is not None
    ):
        log_api_communication(
            "GET",
            request_address,
            "The request was rejected because the address was not approved.",
            None,
            correlation_id,
        )
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
            http_status_code = response.status
            content_type = response.headers.get("Content-Type", "")
            response_bytes = response.read(MAX_REPLY_SIZE_BYTES + 1)
            response_text = response_bytes.decode("utf-8", errors="replace")
            if len(response_bytes) > MAX_REPLY_SIZE_BYTES:
                response_text += "\n[Reply was truncated after the safe size limit.]"
            log_api_communication(
                "GET",
                request_address,
                response_text,
                http_status_code,
                correlation_id,
            )
            json_media_type = content_type.split(";", maxsplit=1)[0].strip().lower()
            if (
                json_media_type != "application/json"
                and not json_media_type.endswith("+json")
            ):
                raise FootballDataError(
                    "ESPN sent information in a format the program cannot read."
                )
    except HTTPError as error:
        error_reply = error.read(MAX_REPLY_SIZE_BYTES + 1).decode(
            "utf-8",
            errors="replace",
        )
        if len(error_reply.encode("utf-8")) > MAX_REPLY_SIZE_BYTES:
            error_reply += "\n[Reply was truncated after the safe size limit.]"
        log_api_communication(
            "GET",
            request_address,
            error_reply or str(error),
            error.code,
            correlation_id,
        )
        raise FootballDataError(
            f"ESPN could not provide the information (web status {error.code}, "
            f"reference {correlation_id}). "
            "Please try again later."
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        log_api_communication(
            "GET",
            request_address,
            f"The request failed: {type(error).__name__}: {error}",
            None,
            correlation_id,
        )
        raise FootballDataError(
            "The program could not connect to ESPN. Check your internet "
            f"connection and try again. Reference: {correlation_id}."
        ) from error

    if len(response_bytes) > MAX_REPLY_SIZE_BYTES:
        raise FootballDataError(
            "ESPN sent more information than the program can safely read. "
            f"Reference: {correlation_id}."
        )

    try:
        reply = json.loads(response_bytes.decode("utf-8"))
    except (JSONDecodeError, UnicodeDecodeError) as error:
        raise FootballDataError(
            "ESPN sent information that the program could not understand. "
            f"Reference: {correlation_id}."
        ) from error

    if not isinstance(reply, dict):
        raise FootballDataError(
            "ESPN sent information in an unexpected format. Please try again later."
        )
    return reply


def get_espn_image(image_address: str) -> bytes:
    """Download a small badge image only from ESPN's image website."""
    correlation_id = str(uuid4())
    address_parts = urlsplit(image_address)
    if (
        address_parts.scheme != "https"
        or address_parts.hostname != ESPN_IMAGE_HOST
        or address_parts.port is not None
        or address_parts.username is not None
        or address_parts.password is not None
    ):
        log_api_communication(
            "GET image",
            image_address,
            "The image request was rejected because the address was not approved.",
            None,
            correlation_id,
        )
        raise FootballDataError(
            "The program stopped a badge address that is not ESPN's approved "
            "image website."
        )

    safe_opener = build_opener(StopWebsiteRedirects())
    image_request = Request(
        image_address,
        headers={"User-Agent": "FootballMonitor/1.0"},
    )
    try:
        with safe_opener.open(
            image_request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            image_bytes = response.read(MAX_IMAGE_SIZE_BYTES + 1)
            image_type = response.headers.get("Content-Type", "unknown")
            image_description = (
                f"Image content type: {image_type}; "
                f"received bytes: {len(image_bytes)}"
            )
            log_api_communication(
                "GET image",
                image_address,
                image_description,
                response.status,
                correlation_id,
            )
    except HTTPError as error:
        log_api_communication(
            "GET image",
            image_address,
            f"The image request failed: {error}",
            error.code,
            correlation_id,
        )
        raise FootballDataError(
            f"ESPN could not provide a badge image (web status {error.code})."
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        log_api_communication(
            "GET image",
            image_address,
            f"The image request failed: {type(error).__name__}: {error}",
            None,
            correlation_id,
        )
        raise FootballDataError(
            "The program could not download a badge image. Check your internet "
            "connection and try again."
        ) from error

    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise FootballDataError(
            "ESPN sent a badge image that is too large to show safely."
        )
    if not image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise FootballDataError(
            "ESPN sent a badge image in a format the program cannot display."
        )
    return image_bytes


def clean_words(value: object, fallback: str = "Not available") -> str:
    """Return useful clean words, or a clear replacement if none are given."""
    if isinstance(value, str) and value.strip():
        return " ".join(value.split())
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return fallback
