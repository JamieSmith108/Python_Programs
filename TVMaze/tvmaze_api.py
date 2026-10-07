"""Find TV program details by asking the TVMaze website."""

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from json import JSONDecodeError
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from activity_log import (
    log_connection_error,
    log_http_error,
    log_request_start,
    log_request_success,
    log_unreadable_reply,
    make_search_reference,
)
from config import AppSettings, NOT_AVAILABLE, SHOW_FIELD_OPTIONS, load_settings
from helpers import make_english_value, remove_html_tags


class ProgramNotFoundError(Exception):
    """Tell the program that TVMaze could not find the requested show."""


class TVMazeError(Exception):
    """Tell the program that TVMaze could not return usable information."""


@dataclass
class ProgramDetails:
    """Hold readable values for every show field returned by TVMaze."""

    fields: dict[str, str]
    image_data: bytes | None = None


def find_program_details(
    program_name: str,
    settings: AppSettings | None = None,
) -> ProgramDetails:
    """Search TVMaze and return details about the best matching program."""
    if settings is None:
        settings = load_settings()

    search_query = urlencode({"q": program_name})
    search_url = f"{settings.tvmaze_api_url}?{search_query}"
    search_reference = make_search_reference()

    try:
        response_body = request_tvmaze(
            search_url,
            "program details",
            settings.request_timeout_seconds,
            search_reference,
        )
    except HTTPError as error:
        if error.code == 404:
            raise ProgramNotFoundError(
                f'No TV program named "{program_name}" was found. '
                f"Search reference: {search_reference}."
            ) from error
        raise TVMazeError(
            f"TVMaze returned an error (HTTP {error.code}). "
            f"Search reference: {search_reference}."
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        raise TVMazeError(
            "Could not connect to TVMaze. Check your internet connection and try again."
            f" Search reference: {search_reference}."
        ) from error

    try:
        program_data = json.loads(response_body.decode("utf-8"))
    except (JSONDecodeError, UnicodeDecodeError) as error:
        log_unreadable_reply(
            search_reference,
            "program details",
            search_url,
            f"The reply was not valid readable JSON: {error}",
        )
        raise TVMazeError(
            "TVMaze sent information that could not be read. "
            f"Search reference: {search_reference}."
        ) from error

    if not isinstance(program_data, dict):
        log_unreadable_reply(
            search_reference,
            "program details",
            search_url,
            "The reply was not a program details object.",
        )
        raise TVMazeError(
            "TVMaze sent information in an unexpected format. "
            f"Search reference: {search_reference}."
        )

    program = make_program_details(program_data)
    if "image" in settings.selected_show_fields:
        picture_url = find_picture_url(program_data.get("image"))
        if picture_url is None:
            program.fields["image"] = "No image is available for this show."
        else:
            try:
                program.image_data = request_tvmaze(
                    picture_url,
                    "show picture",
                    settings.request_timeout_seconds,
                    search_reference,
                )
            except (HTTPError, URLError, TimeoutError, OSError):
                program.fields["image"] = "The show image could not be downloaded."

    return program


def request_tvmaze(
    request_url: str,
    request_part_name: str,
    timeout_seconds: int,
    search_reference: str,
) -> bytes:
    """Send one GET request and write down what happened."""
    request_started_at = log_request_start(
        search_reference,
        request_part_name,
        request_url,
        timeout_seconds,
    )
    request = Request(
        request_url,
        headers={
            "User-Agent": "TVMaze-Show-Finder/1.0",
            "X-Correlation-ID": search_reference,
        },
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read()
            log_request_success(
                search_reference,
                request_part_name,
                request_url,
                response.status,
                response.headers,
                time.monotonic() - request_started_at,
                len(response_body),
            )
            return response_body
    except HTTPError as error:
        log_http_error(
            search_reference,
            request_part_name,
            request_url,
            error.code,
            error.headers or {},
            time.monotonic() - request_started_at,
            error.reason,
        )
        raise
    except (URLError, TimeoutError, OSError) as error:
        log_connection_error(
            search_reference,
            request_part_name,
            request_url,
            time.monotonic() - request_started_at,
            error,
        )
        raise


def make_program_details(program_data: dict[str, object]) -> ProgramDetails:
    """Convert each field in TVMaze's answer into readable words."""
    readable_fields = {
        field_name: format_program_field(field_name, program_data.get(field_name))
        for field_name, _ in SHOW_FIELD_OPTIONS
    }
    return ProgramDetails(fields=readable_fields)


def format_program_field(field_name: str, value: object) -> str:
    """Write one TVMaze field in a clear and friendly way."""
    if value is None:
        return NOT_AVAILABLE

    if field_name == "schedule" and isinstance(value, dict):
        days_value = value.get("days")
        days = (
            ", ".join(day for day in days_value if isinstance(day, str))
            if isinstance(days_value, list)
            else ""
        )
        show_time = value.get("time")
        if isinstance(show_time, str) and show_time.strip() and days:
            return f"{days} at {make_english_time(show_time)}"
        if days:
            return days
        if isinstance(show_time, str) and show_time.strip():
            return make_english_time(show_time)
        return NOT_AVAILABLE

    if field_name == "rating" and isinstance(value, dict):
        average = value.get("average")
        if isinstance(average, (int, float)) and not isinstance(average, bool):
            return f"{average:g} out of 10"
        return NOT_AVAILABLE

    if field_name in {"premiered", "ended"} and isinstance(value, str):
        try:
            show_date = date.fromisoformat(value)
        except ValueError:
            return value
        return f"{show_date:%B} {show_date.day}, {show_date.year}"

    if field_name in {"runtime", "averageRuntime"} and isinstance(value, int):
        return f"{value} minutes"

    if field_name == "updated" and isinstance(value, (int, float)):
        updated_time = datetime.fromtimestamp(value, tz=timezone.utc)
        readable_date = (
            f"{updated_time:%B} {updated_time.day}, {updated_time.year}"
        )
        return f"{readable_date} at {updated_time:%I:%M %p UTC}"

    if field_name == "summary" and isinstance(value, str):
        return remove_html_tags(value) or NOT_AVAILABLE

    if field_name == "image":
        return "The show image is displayed above."

    return make_english_value(value)


def find_picture_url(image_value: object) -> str | None:
    """Find the address of the smaller poster picture."""
    if not isinstance(image_value, dict):
        return None

    medium_image = image_value.get("medium")
    if isinstance(medium_image, str) and medium_image.startswith("https://"):
        return medium_image

    original_image = image_value.get("original")
    if isinstance(original_image, str) and original_image.startswith("https://"):
        return original_image

    return None


def make_english_time(time_text: str) -> str:
    """Change a 24-hour clock time into a familiar 12-hour clock time."""
    try:
        parsed_time = datetime.strptime(time_text.strip(), "%H:%M")
    except ValueError:
        return time_text.strip()

    return parsed_time.strftime("%I:%M %p").lstrip("0")
