"""Find TV program details by asking the TVMaze website."""

import json
from dataclasses import dataclass
from json import JSONDecodeError
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from config import NOT_AVAILABLE, REQUEST_TIMEOUT_SECONDS, TVMAZE_API_URL
from helpers import read_nested_text, read_number, read_text, read_text_list, remove_html_tags


class ShowNotFoundError(Exception):
    """Tell the program that TVMaze could not find the requested show."""


class TVMazeError(Exception):
    """Tell the program that TVMaze could not return usable information."""


@dataclass(frozen=True)
class ShowDetails:
    """Hold the details that the screen shows for a TV program."""

    name: str
    show_type: str
    language: str
    genres: str
    status: str
    premiered: str
    ended: str
    runtime: str
    rating: str
    channel: str
    schedule: str
    official_site: str
    summary: str


def search_for_show(search_text: str) -> ShowDetails:
    """Ask TVMaze for one show and turn its answer into easy-to-use details."""
    query_string = urlencode({"q": search_text})
    request_url = f"{TVMAZE_API_URL}?{query_string}"

    try:
        with urlopen(request_url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            show_data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 404:
            raise ShowNotFoundError(
                f'No TV program named "{search_text}" was found.'
            ) from error
        raise TVMazeError(f"TVMaze returned an error (HTTP {error.code}).") from error
    except (URLError, TimeoutError) as error:
        raise TVMazeError(
            "Could not connect to TVMaze. Check your internet connection and try again."
        ) from error
    except (JSONDecodeError, UnicodeDecodeError) as error:
        raise TVMazeError("TVMaze sent information that could not be read.") from error

    if not isinstance(show_data, dict):
        raise TVMazeError("TVMaze sent information in an unexpected format.")

    return make_show_details(show_data)


def make_show_details(show_data: dict[str, object]) -> ShowDetails:
    """Pick the useful details out of TVMaze's answer."""
    rating_data = show_data.get("rating")
    rating_number = read_number(
        rating_data.get("average") if isinstance(rating_data, dict) else None
    )
    if rating_number is not None:
        rating_value = f"{rating_number:g} out of 10"
    else:
        rating_value = read_nested_text(rating_data, "average")
    if rating_value != NOT_AVAILABLE and rating_number is None:
        rating_value = f"{rating_value} out of 10"

    network = read_nested_text(show_data.get("network"), "name")
    if network == NOT_AVAILABLE:
        network = read_nested_text(show_data.get("webChannel"), "name")

    schedule_data = show_data.get("schedule")
    schedule_days = (
        read_text_list(schedule_data.get("days"))
        if isinstance(schedule_data, dict)
        else NOT_AVAILABLE
    )
    schedule_time = read_nested_text(schedule_data, "time")
    schedule = (
        f"{schedule_days} at {schedule_time}"
        if schedule_days != NOT_AVAILABLE and schedule_time != NOT_AVAILABLE
        else schedule_days
    )

    summary = read_text(show_data.get("summary"), fallback="")
    readable_summary = remove_html_tags(summary) if summary else "Not available"

    return ShowDetails(
        name=read_text(show_data.get("name")),
        show_type=read_text(show_data.get("type")),
        language=read_text(show_data.get("language")),
        genres=read_text_list(show_data.get("genres")),
        status=read_text(show_data.get("status")),
        premiered=read_text(show_data.get("premiered")),
        ended=read_text(show_data.get("ended")),
        runtime=read_text(show_data.get("runtime")),
        rating=rating_value,
        channel=network,
        schedule=schedule,
        official_site=read_text(show_data.get("officialSite")),
        summary=readable_summary,
    )
