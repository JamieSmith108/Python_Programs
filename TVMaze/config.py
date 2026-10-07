"""Default settings and saved settings for the TVMaze show finder."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path


# The settings file lives beside this program and is created when settings are saved.
SETTINGS_FILE = Path(__file__).with_name("settings.json")

# Every top-level show field returned by the TVMaze show endpoint
SHOW_FIELD_OPTIONS = (
    ("id", "Show ID"),
    ("url", "TVMaze page"),
    ("name", "Program name"),
    ("type", "Program type"),
    ("language", "Language"),
    ("genres", "Genres"),
    ("status", "Status"),
    ("runtime", "Episode length"),
    ("averageRuntime", "Average episode length"),
    ("premiered", "First shown"),
    ("ended", "Last shown"),
    ("officialSite", "Official website"),
    ("schedule", "Schedule"),
    ("rating", "Rating"),
    ("weight", "Match weight"),
    ("network", "TV network"),
    ("webChannel", "Web channel"),
    ("dvdCountry", "DVD country"),
    ("externals", "External database IDs"),
    ("image", "Show images"),
    ("summary", "Summary"),
    ("updated", "Last updated"),
    ("_links", "Related episode links"),
)

DEFAULT_SELECTED_SHOW_FIELDS = (
    "name",
    "type",
    "language",
    "genres",
    "status",
    "premiered",
    "ended",
    "runtime",
    "rating",
    "network",
    "webChannel",
    "schedule",
    "officialSite",
    "summary",
)


@dataclass(frozen=True)
class AppSettings:
    """Keep the settings that a person can change in one clear place."""

    window_title: str = "TVMaze Show Finder"
    window_width: int = 720
    window_height: int = 580
    minimum_window_width: int = 520
    minimum_window_height: int = 420
    tvmaze_api_url: str = "https://api.tvmaze.com/singlesearch/shows"
    request_timeout_seconds: int = 10
    selected_show_fields: tuple[str, ...] = DEFAULT_SELECTED_SHOW_FIELDS


class SettingsError(Exception):
    """Explain when saved settings cannot be read or used."""


def load_settings(settings_file: Path = SETTINGS_FILE) -> AppSettings:
    """Load saved settings, or use the defaults when none have been saved."""
    if not settings_file.exists():
        return AppSettings()

    try:
        saved_values = json.loads(settings_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SettingsError(f"Could not read settings: {error}") from error

    if not isinstance(saved_values, dict):
        raise SettingsError("The saved settings must be a JSON object.")

    known_values = asdict(AppSettings())
    for setting_name, setting_value in saved_values.items():
        if setting_name in known_values:
            known_values[setting_name] = setting_value
    if isinstance(known_values["selected_show_fields"], list):
        known_values["selected_show_fields"] = tuple(
            known_values["selected_show_fields"]
        )

    try:
        settings = AppSettings(**known_values)
        check_settings(settings)
    except (TypeError, ValueError) as error:
        raise SettingsError(f"The saved settings are not valid: {error}") from error

    return settings


def save_settings(settings: AppSettings, settings_file: Path = SETTINGS_FILE) -> None:
    """Save the chosen settings so they are remembered next time."""
    try:
        check_settings(settings)
    except ValueError as error:
        raise SettingsError(f"The settings are not valid: {error}") from error

    try:
        settings_file.write_text(
            json.dumps(asdict(settings), indent=4) + "\n",
            encoding="utf-8",
        )
    except OSError as error:
        raise SettingsError(f"Could not save settings: {error}") from error


def check_settings(settings: AppSettings) -> None:
    """Make sure the saved settings have sensible values."""
    if not isinstance(settings.window_title, str):
        raise ValueError("The window title must be text.")
    if not settings.window_title.strip():
        raise ValueError("The window title cannot be empty.")
    if not isinstance(settings.tvmaze_api_url, str):
        raise ValueError("The TVMaze API address must be text.")

    number_settings = {
        "Window width": settings.window_width,
        "Window height": settings.window_height,
        "Minimum window width": settings.minimum_window_width,
        "Minimum window height": settings.minimum_window_height,
        "Request timeout": settings.request_timeout_seconds,
    }
    for setting_label, setting_value in number_settings.items():
        if isinstance(setting_value, bool) or not isinstance(setting_value, int):
            raise ValueError(f"{setting_label} must be a whole number.")
        if setting_value < 1:
            raise ValueError(f"{setting_label} must be greater than zero.")

    if settings.window_width < settings.minimum_window_width:
        raise ValueError("Window width cannot be less than its minimum width.")
    if settings.window_height < settings.minimum_window_height:
        raise ValueError("Window height cannot be less than its minimum height.")

    if not settings.tvmaze_api_url.startswith(("https://", "http://")):
        raise ValueError("The TVMaze API address must start with http:// or https://.")

    if not isinstance(settings.selected_show_fields, tuple):
        raise ValueError("The selected show fields must be a list of field names.")
    available_fields = {field_name for field_name, _ in SHOW_FIELD_OPTIONS}
    if not settings.selected_show_fields:
        raise ValueError("Choose at least one show field to display.")
    if any(
        not isinstance(field_name, str) or field_name not in available_fields
        for field_name in settings.selected_show_fields
    ):
        raise ValueError("One or more selected show fields are not recognized.")
    if len(set(settings.selected_show_fields)) != len(settings.selected_show_fields):
        raise ValueError("A show field cannot be selected more than once.")


# Text shown when TVMaze does not provide a value
NOT_AVAILABLE = "Not available"

# Labels shown in the program
SEARCH_LABEL = "Enter a TV program name:"
SEARCH_BUTTON_TEXT = "Find program"
EXIT_BUTTON_TEXT = "Exit"
WAITING_MESSAGE = "Searching TVMaze..."
WELCOME_MESSAGE = "Enter a program name above, then choose Find program."
