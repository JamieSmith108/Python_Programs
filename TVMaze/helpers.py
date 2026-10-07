"""Small reusable functions used by the TVMaze show finder."""

import re
from collections.abc import Mapping
from html.parser import HTMLParser
import logging

from config import NOT_AVAILABLE


FIELD_LABELS = {
    "averageRuntime": "Average episode length",
    "average": "Average rating",
    "dvdCountry": "DVD country",
    "external": "External ID",
    "externals": "External IDs",
    "href": "Web address",
    "id": "ID",
    "imdb": "IMDb ID",
    "medium": "Medium-sized image",
    "name": "Name",
    "network": "TV network",
    "original": "Full-sized image",
    "previousepisode": "Previous episode",
    "self": "TVMaze page",
    "thetvdb": "TheTVDB ID",
    "timezone": "Time zone",
    "tvrage": "TVRage ID",
    "webChannel": "Web channel",
}


class SummaryTextReader(HTMLParser):
    """Collect readable text from an HTML summary."""

    def __init__(self) -> None:
        """Prepare a place to collect the words in a summary."""
        super().__init__(convert_charrefs=True)
        self.summary_words: list[str] = []

    def handle_data(self, text_piece: str) -> None:
        """Save a piece of ordinary text from the summary."""
        self.summary_words.append(text_piece)

    def handle_starttag(
        self,
        tag: str,
        attributes: list[tuple[str, str | None]],
    ) -> None:
        """Separate words when an HTML block or line break starts."""
        del attributes
        if tag in {"br", "div", "li", "p"}:
            self.summary_words.append(" ")

    def handle_endtag(self, tag: str) -> None:
        """Separate words when an HTML block ends."""
        if tag in {"div", "li", "p"}:
            self.summary_words.append(" ")


def read_text(input_value: object, replacement: str = NOT_AVAILABLE) -> str:
    """Return clean text, or a replacement message when no text is available."""
    if isinstance(input_value, str) and input_value.strip():
        return input_value.strip()

    if isinstance(input_value, (int, float)) and not isinstance(input_value, bool):
        return str(input_value)

    return replacement


def remove_html_tags(summary: str) -> str:
    """Remove HTML tags and extra spaces from a program summary."""
    summary_reader = SummaryTextReader()
    summary_reader.feed(summary)
    summary_reader.close()
    return " ".join("".join(summary_reader.summary_words).split())


def make_english_label(field_name: str) -> str:
    """Turn a technical field name into a readable English label."""
    if field_name in FIELD_LABELS:
        return FIELD_LABELS[field_name]

    words = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", field_name)
    words = words.replace("_", " ").replace("-", " ")
    return " ".join(word.capitalize() for word in words.split())


def make_english_value(value: object) -> str:
    """Turn nested API values into readable text instead of JSON."""
    if value is None:
        return NOT_AVAILABLE

    if isinstance(value, bool):
        return "Yes" if value else "No"

    if isinstance(value, Mapping):
        readable_parts = []
        for nested_name, nested_value in value.items():
            if nested_value is None:
                continue

            readable_value = make_english_value(nested_value)
            if nested_name == "name" and isinstance(nested_value, str):
                readable_parts.insert(0, readable_value)
            else:
                readable_parts.append(
                    f"{make_english_label(str(nested_name))}: {readable_value}"
                )

        return "\n".join(readable_parts) if readable_parts else NOT_AVAILABLE

    if isinstance(value, list):
        readable_items = [
            make_english_value(item)
            for item in value
            if item is not None
        ]
        separator = ", " if all(isinstance(item, str) for item in value) else "; "
        return separator.join(readable_items) if readable_items else NOT_AVAILABLE

    return read_text(value)


def make_one_line(message: str, character_limit: int = 1000) -> str:
    """Remove extra spaces and line breaks from a message."""
    return " ".join(message.split())[:character_limit]


def close_logger_handlers(logger: logging.Logger) -> None:
    """Close every open file used by a logger."""
    for file_handler in logger.handlers[:]:
        logger.removeHandler(file_handler)
        file_handler.close()
