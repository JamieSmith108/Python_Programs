"""Share safe ESPN requests, request addresses, and simple text-cleaning tools."""

import json
from json import JSONDecodeError
from pathlib import Path
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

from config import (
    ESPN_API_HOST,
    ESPN_IMAGE_HOST,
    MAX_IMAGE_SIZE_BYTES,
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
    from logging_service import log_api_communication

    request, correlation_id = make_approved_espn_request(
        request_address,
        ESPN_API_HOST,
        "GET",
        "a web address that is not ESPN's approved football data website",
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
    from logging_service import log_api_communication

    image_request, correlation_id = make_approved_espn_request(
        image_address,
        ESPN_IMAGE_HOST,
        "GET image",
        "a badge address that is not ESPN's approved image website",
    )
    safe_opener = build_opener(StopWebsiteRedirects())
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


def make_approved_espn_request(
    request_address: str,
    approved_host: str,
    communication_type: str,
    rejected_address_message: str,
) -> tuple[Request, str]:
    """Check one ESPN address and prepare its request with a unique reference."""
    from logging_service import log_api_communication

    correlation_id = str(uuid4())
    address_parts = urlsplit(request_address)
    if (
        address_parts.scheme != "https"
        or address_parts.hostname != approved_host
        or address_parts.port is not None
        or address_parts.username is not None
        or address_parts.password is not None
    ):
        log_api_communication(
            communication_type,
            request_address,
            f"The request was rejected because {rejected_address_message}.",
            None,
            correlation_id,
        )
        raise FootballDataError(
            f"The program stopped {rejected_address_message}."
        )

    request = Request(
        request_address,
        headers={"User-Agent": "FootballMonitor/1.0"},
    )
    return request, correlation_id


def update_json_settings_file(
    settings_file: Path,
    new_values: dict[str, object],
) -> None:
    """Update a JSON settings file safely while keeping its other saved values."""
    saved_values: dict[str, object] = {}
    if settings_file.exists():
        try:
            saved_document = json.loads(settings_file.read_text(encoding="utf-8"))
        except (OSError, JSONDecodeError) as error:
            raise ValueError(
                f"The settings file could not be read: {settings_file}"
            ) from error
        if not isinstance(saved_document, dict):
            raise ValueError(
                f"The settings file must contain a JSON object: {settings_file}"
            )
        saved_values = saved_document
    saved_values.update(new_values)

    temporary_file_path: Path | None = None
    try:
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=settings_file.parent,
            delete=False,
        ) as temporary_file:
            temporary_file.write(json.dumps(saved_values, indent=2))
            temporary_file_path = Path(temporary_file.name)
        temporary_file_path.replace(settings_file)
    finally:
        if temporary_file_path is not None and temporary_file_path.exists():
            temporary_file_path.unlink()


def make_espn_api_address(
    api_root: str,
    league_code: str,
    endpoint: str,
    query_values: dict[str, str | int] | None = None,
) -> str:
    """Build one consistent ESPN address for a league and request type."""
    request_address = f"{api_root}/{league_code}/{endpoint.lstrip('/')}"
    if query_values:
        request_address = f"{request_address}?{urlencode(query_values)}"
    return request_address


def get_optional_espn_image(
    image_address: str,
    activity_description: str,
    recovery_advice: str,
) -> bytes | None:
    """Try to get an optional badge and log a clear reason if it is unavailable."""
    from logging_service import log_application_error

    try:
        return get_espn_image(image_address)
    except (FootballDataError, OSError, ValueError) as error:
        log_application_error(
            activity_description,
            str(error),
            recovery_advice,
            error,
        )
        return None


def clean_words(value: object, fallback: str = "Not available") -> str:
    """Return useful clean words, or a clear replacement if none are given."""
    if isinstance(value, str) and value.strip():
        return " ".join(value.split())
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return fallback
