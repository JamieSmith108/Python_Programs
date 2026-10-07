"""Find TV program details by asking the TVMaze website."""

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from json import JSONDecodeError
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

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

    try:
        with urlopen(
            search_url,
            timeout=settings.request_timeout_seconds,
        ) as response:
            program_data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 404:
            raise ProgramNotFoundError(
                f'No TV program named "{program_name}" was found.'
            ) from error
        raise TVMazeError(f"TVMaze returned an error (HTTP {error.code}).") from error
    except (URLError, TimeoutError) as error:
        raise TVMazeError(
            "Could not connect to TVMaze. Check your internet connection and try again."
        ) from error
    except (JSONDecodeError, UnicodeDecodeError) as error:
        raise TVMazeError("TVMaze sent information that could not be read.") from error

    if not isinstance(program_data, dict):
        raise TVMazeError("TVMaze sent information in an unexpected format.")

    program = make_program_details(program_data)
    if "image" in settings.selected_show_fields:
        picture_url = find_picture_url(program_data.get("image"))
        if picture_url is not None:
            try:
                with urlopen(
                    picture_url,
                    timeout=settings.request_timeout_seconds,
                ) as response:
                    program.image_data = response.read()
            except (HTTPError, URLError, TimeoutError, OSError):
                program.fields["image"] = (
                    "The show image could not be downloaded."
                )
        else:
            program.fields["image"] = "No image is available for this show."

    return program


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
        return show_date.strftime("%B %d, %Y").replace(" 0", " ")

    if field_name in {"runtime", "averageRuntime"} and isinstance(value, int):
        return f"{value} minutes"

    if field_name == "updated" and isinstance(value, (int, float)):
        updated_time = datetime.fromtimestamp(value, tz=timezone.utc)
        return (
            updated_time.strftime("%B %d, %Y at %I:%M %p UTC")
            .replace(" 0", " ")
        )

    if field_name == "summary" and isinstance(value, str):
        return remove_html_tags(value) or NOT_AVAILABLE

    if field_name == "image":
        return "The show image is displayed above."

    return make_english_value(value, field_name)


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
        show_time = datetime.strptime(time_text.strip(), "%H:%M")
    except ValueError:
        return time_text.strip()

    return show_time.strftime("%I:%M %p").lstrip("0")
