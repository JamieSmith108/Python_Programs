"""Load and save external settings for the Football Monitor log files."""

from dataclasses import dataclass
import json
import os
from pathlib import Path

from config import DEFAULT_SELECTED_LEAGUES, FOOTBALL_LEAGUES
from helpers import update_json_settings_file


APP_DATA_FOLDER_NAME = "FootballMonitor"
SETTINGS_FILE_NAME = "settings.json"


class SettingsError(Exception):
    """Explain when the external log settings cannot be read or saved."""


@dataclass(frozen=True)
class LogFileSettings:
    """Keep the three user-selected log paths together."""

    api_communications_log: str
    application_log: str
    testing_log: str


def get_settings_folder() -> Path:
    """Find a per-user settings folder outside the program code folder."""
    roaming_folder = os.environ.get("APPDATA")
    if roaming_folder:
        return Path(roaming_folder) / APP_DATA_FOLDER_NAME
    return Path.home() / "AppData" / "Roaming" / APP_DATA_FOLDER_NAME


def get_settings_file_path() -> Path:
    """Return the full path of the external JSON configuration file."""
    return get_settings_folder() / SETTINGS_FILE_NAME


def get_default_log_settings() -> LogFileSettings:
    """Choose separate log files in the user's local application data folder."""
    local_folder = Path(
        os.environ.get(
            "LOCALAPPDATA",
            str(Path.home() / "AppData" / "Local"),
        )
    )
    log_folder = local_folder / APP_DATA_FOLDER_NAME / "Logs"
    return LogFileSettings(
        api_communications_log=str(log_folder / "API_communications_log.txt"),
        application_log=str(log_folder / "application_log.txt"),
        testing_log=str(log_folder / "testing_log.txt"),
    )


def load_log_settings() -> LogFileSettings:
    """Read the saved paths or create an external file with safe defaults."""
    settings_file = get_settings_file_path()
    if not settings_file.exists():
        default_settings = get_default_log_settings()
        save_log_settings(default_settings)
        return default_settings

    saved_values = read_settings_document()
    settings = LogFileSettings(
        api_communications_log=get_saved_path(
            saved_values,
            "api_communications_log",
        ),
        application_log=get_saved_path(saved_values, "application_log"),
        testing_log=get_saved_path(saved_values, "testing_log"),
    )
    validate_log_settings(settings)
    return settings


def get_saved_path(saved_values: dict[str, object], setting_name: str) -> str:
    """Read one saved path and use its default when older settings omit it."""
    default_settings = get_default_log_settings()
    default_path_by_name = {
        "api_communications_log": default_settings.api_communications_log,
        "application_log": default_settings.application_log,
        "testing_log": default_settings.testing_log,
    }
    saved_path = saved_values.get(setting_name)
    if saved_path is None:
        return default_path_by_name[setting_name]
    if not isinstance(saved_path, str) or not saved_path.strip():
        raise SettingsError(
            f"The setting '{setting_name}' must contain a file path."
        )
    return str(Path(saved_path).expanduser().resolve())


def save_log_settings(settings: LogFileSettings) -> None:
    """Save the log file paths outside the program's source code folder."""
    validate_log_settings(settings)
    save_settings_values(make_log_settings_values(settings), "log settings")


def load_selected_leagues() -> list[str]:
    """Read the league checkboxes or choose the local leagues by default."""
    settings_file = get_settings_file_path()
    if not settings_file.exists():
        return list(DEFAULT_SELECTED_LEAGUES)
    saved_values = read_settings_document()
    saved_leagues = saved_values.get("selected_leagues")
    if saved_leagues is None:
        return list(DEFAULT_SELECTED_LEAGUES)
    if not isinstance(saved_leagues, list) or not all(
        isinstance(league_name, str) for league_name in saved_leagues
    ):
        raise SettingsError(
            "The selected leagues setting must be a list of league names. "
            f"Check the settings file: {settings_file}"
        )
    selected_names = set(saved_leagues)
    return [
        league_name
        for league_name in FOOTBALL_LEAGUES
        if league_name in selected_names
    ]


def save_application_settings(
    log_settings: LogFileSettings,
    selected_leagues: list[str],
) -> None:
    """Save log paths and selected leagues together in one settings update."""
    validate_log_settings(log_settings)
    unknown_leagues = set(selected_leagues) - set(FOOTBALL_LEAGUES)
    if unknown_leagues:
        raise SettingsError(
            "Only leagues from the available league list can be selected."
        )
    settings_values = make_log_settings_values(log_settings)
    settings_values["selected_leagues"] = [
        league_name
        for league_name in FOOTBALL_LEAGUES
        if league_name in selected_leagues
    ]
    save_settings_values(settings_values, "application settings")


def make_log_settings_values(
    settings: LogFileSettings,
) -> dict[str, str]:
    """Make the three log paths ready to save in the settings file."""
    return {
        "api_communications_log": str(
            Path(settings.api_communications_log).expanduser().resolve()
        ),
        "application_log": str(
            Path(settings.application_log).expanduser().resolve()
        ),
        "testing_log": str(
            Path(settings.testing_log).expanduser().resolve()
        ),
    }


def read_settings_document() -> dict[str, object]:
    """Read the shared JSON settings without dropping saved preferences."""
    settings_file = get_settings_file_path()
    if not settings_file.exists():
        return {}
    try:
        saved_values = json.loads(settings_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SettingsError(
            "The settings file could not be read. Check that it is valid JSON "
            f"and that this account can read it: {settings_file}"
        ) from error
    if not isinstance(saved_values, dict):
        raise SettingsError(
            f"The settings file must contain a JSON object: {settings_file}"
        )
    return saved_values


def save_settings_values(
    new_values: dict[str, object],
    settings_description: str,
) -> None:
    """Save setting changes and explain read or write problems clearly."""
    settings_file = get_settings_file_path()
    try:
        update_json_settings_file(settings_file, new_values)
    except ValueError as error:
        raise SettingsError(str(error)) from error
    except OSError as error:
        raise SettingsError(
            f"The {settings_description} could not be saved. Check that this "
            f"account can write to {settings_file.parent}."
        ) from error


def validate_log_settings(settings: LogFileSettings) -> None:
    """Require three different log paths outside the installed code folder."""
    log_paths = [
        Path(settings.api_communications_log).expanduser().resolve(),
        Path(settings.application_log).expanduser().resolve(),
        Path(settings.testing_log).expanduser().resolve(),
    ]
    if len({str(path).casefold() for path in log_paths}) != len(log_paths):
        raise SettingsError("Choose a different file for each type of log.")

    code_folder = Path(__file__).resolve().parent
    for log_path in log_paths:
        if log_path == code_folder or code_folder in log_path.parents:
            raise SettingsError(
                "Log files must be stored outside the Football Monitor "
                "program folder. Choose a folder in your user profile instead."
            )
        if not log_path.name:
            raise SettingsError("Each log setting must name a file.")
