"""Small reusable functions used by the TVMaze show finder."""

from __future__ import annotations

import re
from collections.abc import Mapping
import hashlib
from html.parser import HTMLParser
import logging
from io import BytesIO
from logging.handlers import RotatingFileHandler
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, unquote, urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)

if TYPE_CHECKING:
    from PIL import Image
    from PIL import ImageTk


NOT_AVAILABLE = "Not available"
TVMAZE_API_HOST = "api.tvmaze.com"
TVMAZE_IMAGE_HOST = "static.tvmaze.com"
TVMAZE_API_PATH = "/singlesearch/shows"
TVMAZE_SEARCH_PATH = "/search/shows"
TVMAZE_IMAGE_PATH = "/uploads/images/"
ALLOWED_IMAGE_FILE_ENDINGS = (".jpg", ".jpeg", ".png", ".webp")
MAX_ALLOWED_SEARCH_NAME_LENGTH = 200
MAX_ALLOWED_SEARCH_QUERY_LENGTH = (MAX_ALLOWED_SEARCH_NAME_LENGTH * 12) + 2
MAX_ALLOWED_REQUEST_TIMEOUT_SECONDS = 120


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


def read_whole_number(field_name: str, typed_value: str) -> int:
    """Turn a settings box into a number and explain mistakes in plain words."""
    try:
        return int(typed_value.strip())
    except ValueError as error:
        raise ValueError(f"{field_name} must be a whole number.") from error


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


def make_small_picture(
    picture_data: bytes,
    maximum_size: tuple[int, int],
) -> Image.Image:
    """Make a smaller copy of a picture so it fits neatly in a window."""
    from PIL import Image

    with Image.open(BytesIO(picture_data)) as original_picture:
        original_picture.thumbnail(maximum_size)
        return original_picture.copy()


def make_photo_image(
    picture_data: bytes,
    maximum_size: tuple[int, int],
) -> ImageTk.PhotoImage:
    """Resize picture bytes and prepare the smaller picture for a Tk window."""
    from PIL import ImageTk

    small_picture = make_small_picture(picture_data, maximum_size)
    return ImageTk.PhotoImage(small_picture)


def make_scrollable_frame(
    parent: tk.Misc,
    height: int | None = None,
) -> tuple[tk.Canvas, ttk.Frame]:
    """Build one shared scrollable list so every screen scrolls the same way."""
    canvas_options = {"highlightthickness": 0}
    if height is not None:
        canvas_options["height"] = height
    canvas = tk.Canvas(parent, **canvas_options)
    scroll_bar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scroll_bar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scroll_bar.pack(side="right", fill="y")

    contents = ttk.Frame(canvas)
    canvas_window = canvas.create_window((0, 0), window=contents, anchor="nw")
    contents.bind(
        "<Configure>",
        lambda event: update_scrollable_frame_area(canvas, event),
    )
    canvas.bind(
        "<Configure>",
        lambda event: fit_scrollable_frame_width(canvas, canvas_window, event),
    )
    return canvas, contents


def update_scrollable_frame_area(canvas: tk.Canvas, event: tk.Event) -> None:
    """Update the scroll range so a person can reach every row."""
    del event
    canvas.configure(scrollregion=canvas.bbox("all"))


def fit_scrollable_frame_width(
    canvas: tk.Canvas,
    canvas_window: int,
    event: tk.Event,
) -> None:
    """Stretch the list to the visible width so labels do not get cut off."""
    canvas.itemconfigure(canvas_window, width=event.width)


def show_read_only_text_window(
    parent: tk.Misc,
    window_title: str,
    text_contents: str,
    outside_change_was_found: bool = False,
) -> tk.Toplevel:
    """Show saved notes in a window that blocks changes and offers copying."""
    text_window = tk.Toplevel(parent)
    text_window.title(window_title)
    text_window.geometry("760x520")
    text_window.transient(parent)

    viewer_message = "This file is read-only here. You can select and copy its words."
    if outside_change_was_found:
        viewer_message = (
            "Warning: This log does not match its saved checksum. "
            "It may have been changed outside this program. "
            + viewer_message
        )
    ttk.Label(
        text_window,
        text=viewer_message,
        wraplength=720,
    ).pack(anchor="w", padx=12, pady=12)

    text_area_frame = ttk.Frame(text_window, padding=(12, 0, 12, 12))
    text_area_frame.pack(fill="both", expand=True)
    text_area = tk.Text(text_area_frame, wrap="word", state="normal")
    scroll_bar = ttk.Scrollbar(
        text_area_frame,
        orient="vertical",
        command=text_area.yview,
    )
    text_area.configure(yscrollcommand=scroll_bar.set)
    text_area.pack(side="left", fill="both", expand=True)
    scroll_bar.pack(side="right", fill="y")
    text_area.insert("1.0", text_contents)
    text_area.configure(state="disabled")

    warning_state = {"shown": False}
    text_area.bind(
        "<KeyPress>",
        lambda event: block_read_only_text_change(
            event,
            text_window,
            warning_state,
        ),
    )
    for edit_event in ("<<Paste>>", "<<Cut>>", "<<Clear>>"):
        text_area.bind(
            edit_event,
            lambda event: block_read_only_text_change(
                event,
                text_window,
                warning_state,
                is_edit_event=True,
            ),
        )
    return text_window


def block_read_only_text_change(
    event: tk.Event,
    parent: tk.Misc,
    warning_state: dict[str, bool],
    is_edit_event: bool = False,
) -> str | None:
    """Stop edit keys and warn once while still allowing reading and copying."""
    edit_keys = {"BackSpace", "Delete", "Return", "KP_Enter"}
    is_edit_key = (
        event.keysym in edit_keys
        or bool(event.char and event.char.isprintable())
    )
    if not is_edit_key and not is_edit_event:
        return None

    if not warning_state["shown"]:
        messagebox.showwarning(
            "This log is read-only",
            "Log files are kept as records and cannot be changed in this window.",
            parent=parent,
        )
        warning_state["shown"] = True
    return "break"


def is_allowed_tvmaze_api_address(address: str) -> bool:
    """Check that an address points to TVMaze's official show search."""
    return is_trusted_tvmaze_address(
        address,
        TVMAZE_API_HOST,
        TVMAZE_API_PATH,
    )


def is_allowed_tvmaze_image_address(address: str) -> bool:
    """Check that an address points to an image on TVMaze's picture website."""
    if not is_trusted_tvmaze_address(
        address,
        TVMAZE_IMAGE_HOST,
        TVMAZE_IMAGE_PATH,
        path_must_start_with=True,
    ):
        return False

    return urlsplit(address).path.lower().endswith(ALLOWED_IMAGE_FILE_ENDINGS)


def is_allowed_tvmaze_request_address(address: str) -> bool:
    """Allow only the official TVMaze search and picture addresses."""
    if is_allowed_tvmaze_image_address(address):
        return True

    if not isinstance(address, str):
        return False

    try:
        address_parts = urlsplit(address)
        allowed_api_path = address_parts.path in {
            TVMAZE_API_PATH,
            TVMAZE_SEARCH_PATH,
        }
        if not allowed_api_path or not is_trusted_tvmaze_address(
            address,
            TVMAZE_API_HOST,
            address_parts.path,
            query_is_allowed=True,
        ):
            return False

        query_text = address_parts.query
        if len(query_text) > MAX_ALLOWED_SEARCH_QUERY_LENGTH:
            return False
        query_values = parse_qs(query_text, strict_parsing=True)
    except ValueError:
        return False

    return (
        set(query_values) == {"q"}
        and len(query_values["q"]) == 1
        and bool(query_values["q"][0])
        and len(query_values["q"][0]) <= MAX_ALLOWED_SEARCH_NAME_LENGTH
    )


def is_trusted_tvmaze_address(
    address: str,
    trusted_host: str,
    trusted_path: str,
    path_must_start_with: bool = False,
    query_is_allowed: bool = False,
) -> bool:
    """Check the secure website, exact server, and allowed part of an address."""
    if not isinstance(address, str) or not address or any(
        ord(character) <= 32 or character == "\\"
        for character in address
    ):
        return False
    if "#" in address or (not query_is_allowed and "?" in address):
        return False

    try:
        address_parts = urlsplit(address)
        address_host = address_parts.hostname
        address_port = address_parts.port
    except ValueError:
        return False

    if (
        address_parts.scheme != "https"
        or address_host != trusted_host
        or address_port is not None
        or address_parts.username is not None
        or address_parts.password is not None
        or (address_parts.query and not query_is_allowed)
        or address_parts.fragment
    ):
        return False

    if path_must_start_with:
        decoded_path = unquote(address_parts.path)
        if "%" in decoded_path or "\\" in decoded_path:
            return False
        path_parts = decoded_path.lower().split("/")
        if "." in path_parts or ".." in path_parts:
            return False
        return decoded_path.startswith(trusted_path)
    return address_parts.path == trusted_path


class DoNotFollowWebsiteRedirects(HTTPRedirectHandler):
    """Stop a trusted website from sending requests to a different address."""

    def redirect_request(
        self,
        request: Request,
        response: object,
        status_code: int,
        reason: str,
        response_headers: object,
        new_address: str,
    ) -> None:
        """Refuse every redirect so a website cannot choose another server."""
        del request, response, status_code, reason, response_headers, new_address
        return None


class ChecksumRotatingFileHandler(RotatingFileHandler):
    """Keep a checksum so later changes to the active log can be noticed."""

    def __init__(
        self,
        log_file_path: str | Path,
        maximum_file_size: int,
        older_file_count: int,
    ) -> None:
        """Open a rotating log and remember its starting checksum."""
        super().__init__(
            log_file_path,
            maxBytes=maximum_file_size,
            backupCount=older_file_count,
            encoding="utf-8",
        )
        self.checksum_file_path = Path(f"{log_file_path}.sha256")
        self.outside_change_was_found = False

        if self.checksum_file_path.exists():
            self.outside_change_was_found = not log_file_matches_saved_checksum(
                log_file_path,
                self.checksum_file_path,
            )
        else:
            save_log_checksum(log_file_path, self.checksum_file_path)

    def emit(self, record: logging.LogRecord) -> None:
        """Write an app note and update its checksum unless outside edits exist."""
        if not self.outside_change_was_found:
            self.outside_change_was_found = not log_file_matches_saved_checksum(
                self.baseFilename,
                self.checksum_file_path,
            )

        super().emit(record)

        if not self.outside_change_was_found:
            save_log_checksum(self.baseFilename, self.checksum_file_path)


def make_file_checksum(file_path: str | Path) -> str:
    """Make a SHA-256 checksum from a file's current contents."""
    checksum = hashlib.sha256()
    with Path(file_path).open("rb") as file_contents:
        for file_piece in iter(lambda: file_contents.read(64_000), b""):
            checksum.update(file_piece)
    return checksum.hexdigest()


def save_log_checksum(
    log_file_path: str | Path,
    checksum_file_path: str | Path,
) -> None:
    """Save the current log checksum beside the log for later comparison."""
    log_path = Path(log_file_path)
    checksum_path = Path(checksum_file_path)
    checksum_path.write_text(make_file_checksum(log_path) + "\n", encoding="ascii")


def log_file_matches_saved_checksum(
    log_file_path: str | Path,
    checksum_file_path: str | Path,
) -> bool:
    """Check whether a log still matches the checksum saved by the app."""
    log_path = Path(log_file_path)
    checksum_path = Path(checksum_file_path)
    if not log_path.is_file() or not checksum_path.is_file():
        return False

    try:
        saved_checksum = checksum_path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        return False
    return saved_checksum == make_file_checksum(log_path)


def open_trusted_tvmaze_request(request: Request, timeout_seconds: int):
    """Open a checked TVMaze address without following any redirects."""
    if not is_allowed_tvmaze_request_address(request.full_url):
        raise ValueError("The address is not an approved TVMaze website address.")
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, int)
        or not 1 <= timeout_seconds <= MAX_ALLOWED_REQUEST_TIMEOUT_SECONDS
    ):
        raise ValueError(
            "The website wait limit must be a whole number from 1 to 120 seconds."
        )

    safe_opener = build_opener(DoNotFollowWebsiteRedirects())
    return safe_opener.open(request, timeout=timeout_seconds)


def start_rotating_file_log(
    logger_name: str,
    log_file_path: str | Path,
    opening_message: str,
    location_message: str,
) -> None:
    """Open a rotating log file and write a helpful start-up message."""
    log_file = Path(log_file_path).expanduser()
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    log_format = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = ChecksumRotatingFileHandler(
        log_file,
        maximum_file_size=1_000_000,
        older_file_count=3,
    )
    file_handler.setFormatter(log_format)

    close_logger_handlers(logger)
    logger.addHandler(file_handler)
    logger.info(opening_message)
    logger.info("%s %s", location_message, log_file)


def close_logger_handlers(logger: logging.Logger) -> None:
    """Close every open file used by a logger."""
    for file_handler in logger.handlers[:]:
        logger.removeHandler(file_handler)
        file_handler.close()


def stop_rotating_file_log(logger_name: str) -> None:
    """Close one named log so both app logs clean up in the same way."""
    close_logger_handlers(logging.getLogger(logger_name))


def read_log_file(logger_name: str, log_file_path: str | Path) -> str:
    """Flush and read one log so its latest note is ready for checking."""
    logger = logging.getLogger(logger_name)
    for file_handler in logger.handlers:
        file_handler.flush()
    return Path(log_file_path).read_text(encoding="utf-8")
