"""Load and save external settings for the Football Monitor log files."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile


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

    try:
        saved_values = json.loads(settings_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SettingsError(
            "The log settings file could not be read. Check that it is valid "
            f"JSON and that this account can read it: {settings_file}"
        ) from error

    if not isinstance(saved_values, dict):
        raise SettingsError(
            f"The log settings file must contain a JSON object: {settings_file}"
        )
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
    settings_file = get_settings_file_path()
    try:
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_json = json.dumps(
            {
                "api_communications_log": str(
                    Path(settings.api_communications_log).expanduser().resolve()
                ),
                "application_log": str(
                    Path(settings.application_log).expanduser().resolve()
                ),
                "testing_log": str(
                    Path(settings.testing_log).expanduser().resolve()
                ),
            },
            indent=2,
        )
        temporary_file_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=settings_file.parent,
                delete=False,
            ) as temporary_file:
                temporary_file.write(settings_json)
                temporary_file_path = Path(temporary_file.name)
            temporary_file_path.replace(settings_file)
        finally:
            if temporary_file_path is not None and temporary_file_path.exists():
                temporary_file_path.unlink()
    except OSError as error:
        raise SettingsError(
            "The log settings could not be saved. Check that this account can "
            f"write to {settings_file.parent}."
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
