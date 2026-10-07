"""Small reusable functions used by the TVMaze show finder."""

from collections.abc import Mapping
from html.parser import HTMLParser

from config import NOT_AVAILABLE


class SummaryTextParser(HTMLParser):
    """Collect readable text from an HTML summary."""

    def __init__(self) -> None:
        """Prepare a place to collect the words in a summary."""
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []

    def handle_data(self, data: str) -> None:
        """Save a piece of ordinary text from the summary."""
        self.text_parts.append(data)

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        """Separate words when an HTML block or line break starts."""
        del _attrs
        if tag in {"br", "div", "li", "p"}:
            self.text_parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        """Separate words when an HTML block ends."""
        if tag in {"div", "li", "p"}:
            self.text_parts.append(" ")


def read_text(value: object, fallback: str = NOT_AVAILABLE) -> str:
    """Turn a text or number into readable text, or use the fallback."""
    if isinstance(value, str) and value.strip():
        return value.strip()

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)

    return fallback


def read_number(value: object) -> float | None:
    """Return a numeric value, or None when the value is not a number."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)

    return None


def read_text_list(value: object) -> str:
    """Join a list of words into one readable line."""
    if not isinstance(value, list):
        return NOT_AVAILABLE

    words = [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return ", ".join(words) if words else NOT_AVAILABLE


def read_nested_text(value: object, key: str) -> str:
    """Read a text value from a dictionary inside another value."""
    if not isinstance(value, Mapping):
        return NOT_AVAILABLE

    return read_text(value.get(key))


def remove_html_tags(summary: str) -> str:
    """Remove HTML tags and extra spaces from a program summary."""
    parser = SummaryTextParser()
    parser.feed(summary)
    parser.close()
    return " ".join("".join(parser.text_parts).split())
