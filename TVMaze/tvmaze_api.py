"""Find TV program details by asking the TVMaze website."""

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from json import JSONDecodeError
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request

from api_activity_logging import (
    log_api_connection_error,
    log_api_http_error,
    log_api_request_start,
    log_successful_api_reply,
    log_unreadable_api_reply,
    make_api_search_reference,
)
from config import (
    AppSettings,
    NOT_AVAILABLE,
    SHOW_FIELD_OPTIONS,
    check_settings,
    load_settings,
)
from application_logging import log_application_error
from helpers import (
    TVMAZE_API_PATH,
    TVMAZE_API_HOST,
    TVMAZE_SEARCH_PATH,
    is_allowed_tvmaze_request_address,
    is_allowed_tvmaze_image_address,
    make_english_value,
    open_trusted_tvmaze_request,
    remove_html_tags,
)

MAX_PROGRAM_NAME_CHARACTERS = 200
MAX_API_REPLY_SIZE_BYTES = 5_000_000
MAX_PICTURE_REPLY_SIZE_BYTES = 10_000_000
ALLOWED_PICTURE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


class ProgramNotFoundError(Exception):
    """Tell the program that TVMaze could not find the requested show."""


class TVMazeError(Exception):
    """Tell the program that TVMaze could not return usable information."""


@dataclass
class ProgramDetails:
    """Hold readable values for every show field returned by TVMaze."""

    fields: dict[str, str]
    image_data: bytes | None = None


@dataclass
class ProgramChoice:
    """Keep one matching show and the years it was on television."""

    program: ProgramDetails
    years_ran: str


def find_program_details(
    program_name: str,
    settings: AppSettings | None = None,
) -> ProgramDetails:
    """Search TVMaze and return details about the best matching program."""
    settings, search_url, search_reference = prepare_program_search(
        program_name,
        settings,
        use_matching_list=False,
    )

    program_data = request_program_reply(
        search_url,
        "program details",
        settings,
        search_reference,
        dict,
    )
    if not isinstance(program_data, dict):
        raise TVMazeError("TVMaze did not return details for the chosen program.")
    program = make_program_details(program_data)
    add_program_picture(program, program_data, settings, search_reference, search_url)
    return program


def find_program_choices(
    program_name: str,
    settings: AppSettings | None = None,
) -> list[ProgramChoice]:
    """Find same-name shows so a person can choose the right one."""
    settings, search_url, search_reference = prepare_program_search(
        program_name,
        settings,
        use_matching_list=True,
    )
    search_reply = request_program_reply(
        search_url,
        "matching program list",
        settings,
        search_reference,
        list,
    )
    if not isinstance(search_reply, list):
        raise TVMazeError("TVMaze did not return a list of matching programs.")

    matching_programs = [
        result["show"]
        for result in search_reply
        if isinstance(result, dict)
        and isinstance(result.get("show"), dict)
        and isinstance(result["show"].get("name"), str)
    ]
    if not matching_programs:
        raise ProgramNotFoundError(
            f'No TV program named "{program_name}" was found. '
            f"Search reference: {search_reference}."
        )

    same_name_programs = [
        show_data
        for show_data in matching_programs
        if show_data["name"].strip().casefold() == program_name.strip().casefold()
    ]
    chosen_programs = same_name_programs or [matching_programs[0]]

    program_choices = []
    for show_data in chosen_programs:
        program = make_program_details(show_data)
        add_program_picture(
            program,
            show_data,
            settings,
            search_reference,
            search_url,
            always_include_picture=True,
        )
        program_choices.append(
            ProgramChoice(
                program=program,
                years_ran=make_program_years(
                    show_data.get("premiered"),
                    show_data.get("ended"),
                ),
            )
        )

    return program_choices


def prepare_program_search(
    program_name: str,
    settings: AppSettings | None,
    use_matching_list: bool,
) -> tuple[AppSettings, str, str]:
    """Check search choices and build a safe address before connecting."""
    if not isinstance(program_name, str) or not program_name.strip():
        raise TVMazeError("Enter a TV program name made up of letters or numbers.")
    if len(program_name) > MAX_PROGRAM_NAME_CHARACTERS:
        raise TVMazeError(
            f"Keep the program name to {MAX_PROGRAM_NAME_CHARACTERS} characters or fewer."
        )

    if settings is None:
        settings = load_settings()
    try:
        check_settings(settings)
    except ValueError as error:
        raise TVMazeError(f"The saved settings are not valid: {error}") from error

    search_path = (
        TVMAZE_SEARCH_PATH
        if use_matching_list
        else TVMAZE_API_PATH
    )
    search_query = urlencode({"q": program_name})
    search_url = f"https://{TVMAZE_API_HOST}{search_path}?{search_query}"
    search_reference = make_api_search_reference()
    return settings, search_url, search_reference


def request_program_reply(
    search_url: str,
    request_part_name: str,
    settings: AppSettings,
    search_reference: str,
    expected_data_type: type,
) -> dict | list:
    """Get and check a TVMaze reply so every search handles errors alike."""
    try:
        response_body = request_tvmaze(
            search_url,
            request_part_name,
            settings.request_timeout_seconds,
            search_reference,
        )
    except HTTPError as error:
        if error.code == 404:
            raise ProgramNotFoundError(
                "TVMaze could not find a matching TV program. "
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
        log_unreadable_api_reply(
            search_reference,
            request_part_name,
            search_url,
            f"The reply was not valid readable JSON: {error}",
        )
        raise TVMazeError(
            "TVMaze sent information that could not be read. "
            f"Search reference: {search_reference}."
        ) from error

    if not isinstance(program_data, expected_data_type):
        log_unreadable_api_reply(
            search_reference,
            request_part_name,
            search_url,
            "The reply did not have the expected kind of program information.",
        )
        raise TVMazeError(
            "TVMaze sent information in an unexpected format. "
            f"Search reference: {search_reference}."
        )

    return program_data


def add_program_picture(
    program: ProgramDetails,
    program_data: dict[str, object],
    settings: AppSettings,
    search_reference: str,
    search_url: str,
    always_include_picture: bool = False,
) -> None:
    """Download a trusted show picture when pictures are part of the results."""
    if not always_include_picture and "image" not in settings.selected_show_fields:
        return

    picture_url = find_picture_url(program_data.get("image"))
    if picture_url is None:
        image_value = program_data.get("image")
        if isinstance(image_value, dict) and any(image_value.values()):
            log_unreadable_api_reply(
                search_reference,
                "show picture",
                search_url,
                "TVMaze returned a picture address that is not from its "
                "approved picture website.",
            )
            program.fields["image"] = (
                "The show picture address was not from the TVMaze picture website."
            )
        else:
            program.fields["image"] = "No image is available for this show."
        return

    try:
        program.image_data = request_tvmaze(
            picture_url,
            "show picture",
            settings.request_timeout_seconds,
            search_reference,
        )
    except (HTTPError, URLError, TimeoutError, OSError, TVMazeError) as error:
        log_application_error("downloading a show picture", error)
        program.fields["image"] = "The show image could not be downloaded."


def make_program_years(premiered: object, ended: object) -> str:
    """Describe the start and end years in a short, familiar way."""
    first_year = get_program_year(premiered)
    last_year = get_program_year(ended)

    if first_year and last_year:
        return f"{first_year} to {last_year}"
    if first_year:
        return f"{first_year} to present"
    if last_year:
        return f"Start year unknown to {last_year}"
    return "Years not available"


def get_program_year(date_value: object) -> str | None:
    """Read a four-digit year only when TVMaze gives a real calendar date."""
    if not isinstance(date_value, str):
        return None
    try:
        return str(date.fromisoformat(date_value).year)
    except ValueError:
        return None


def request_tvmaze(
    request_url: str,
    request_part_name: str,
    timeout_seconds: int,
    search_reference: str,
) -> bytes:
    """Send one GET request and record the API connection details."""
    if not is_allowed_tvmaze_request_address(request_url):
        raise TVMazeError(
            "The program stopped an address that is not an approved TVMaze website."
        )

    request_started_at = log_api_request_start(
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
        with open_trusted_tvmaze_request(request, timeout_seconds) as response:
            content_type = response.headers.get("content-type", "")
            response_type = content_type.split(";", maxsplit=1)[0].strip().lower()
            correct_response_type = (
                response_type in ALLOWED_PICTURE_CONTENT_TYPES
                if request_part_name == "show picture"
                else response_type == "application/json"
            )
            if not correct_response_type:
                problem = (
                    f"The server returned an unexpected type of information: "
                    f"{content_type or 'no content type was provided'}."
                )
                log_unreadable_api_reply(
                    search_reference,
                    request_part_name,
                    request_url,
                    problem,
                )
                raise TVMazeError(
                    "TVMaze sent information in an unexpected format. "
                    f"Search reference: {search_reference}."
                )

            expected_size_limit = (
                MAX_PICTURE_REPLY_SIZE_BYTES
                if request_part_name == "show picture"
                else MAX_API_REPLY_SIZE_BYTES
            )
            response_body = response.read(expected_size_limit + 1)
            if len(response_body) > expected_size_limit:
                problem = (
                    f"The reply was larger than the allowed "
                    f"{expected_size_limit} bytes."
                )
                log_unreadable_api_reply(
                    search_reference,
                    request_part_name,
                    request_url,
                    problem,
                )
                raise TVMazeError(
                    "TVMaze sent a reply that was too large to use safely. "
                    f"Search reference: {search_reference}."
                )
            log_successful_api_reply(
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
        log_api_http_error(
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
        log_api_connection_error(
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
    if isinstance(medium_image, str) and is_allowed_tvmaze_image_address(
        medium_image
    ):
        return medium_image

    original_image = image_value.get("original")
    if isinstance(original_image, str) and is_allowed_tvmaze_image_address(
        original_image
    ):
        return original_image

    return None


def make_english_time(time_text: str) -> str:
    """Change a 24-hour clock time into a familiar 12-hour clock time."""
    try:
        parsed_time = datetime.strptime(time_text.strip(), "%H:%M")
    except ValueError:
        return time_text.strip()

    return parsed_time.strftime("%I:%M %p").lstrip("0")
