"""Write, read, and check the Football Monitor's three log files."""

import hashlib
import json
import logging
import os
from pathlib import Path
import stat
import threading
import traceback
from typing import Literal

from log_settings import LogFileSettings, get_settings_folder


LogName = Literal[
    "api_communications_log",
    "application_log",
    "testing_log",
]
LOGGER_NAME_BY_LOG = {
    "api_communications_log": "football_monitor.api",
    "application_log": "football_monitor.application",
    "testing_log": "football_monitor.testing",
}
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_integrity_lock = threading.RLock()
_integrity_manifest_path = get_settings_folder() / "log_checksums.json"
_integrity_warnings: list[str] = []
_logging_warnings: list[str] = []


def configure_log_files(settings: LogFileSettings) -> None:
    """Connect the standard logging package to the configured log files."""
    global _integrity_manifest_path

    _integrity_warnings.clear()
    _logging_warnings.clear()
    _integrity_manifest_path = get_settings_folder() / "log_checksums.json"
    settings_by_name = {
        "api_communications_log": settings.api_communications_log,
        "application_log": settings.application_log,
        "testing_log": settings.testing_log,
    }
    for log_name, logger_name in LOGGER_NAME_BY_LOG.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        remove_logger_handlers(logger)
        log_path = Path(settings_by_name[log_name]).expanduser().resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if not prepare_integrity_record(log_name, log_path):
            continue
        logger.addHandler(
            IntegrityCheckedFileHandler(log_name, log_path)
        )


def remove_logger_handlers(logger: logging.Logger) -> None:
    """Close old log handlers before changing a saved log file path."""
    for old_handler in logger.handlers[:]:
        logger.removeHandler(old_handler)
        old_handler.close()


def close_log_files() -> None:
    """Close all configured file handlers after a focused logging test."""
    for logger_name in LOGGER_NAME_BY_LOG.values():
        remove_logger_handlers(logging.getLogger(logger_name))


class IntegrityCheckedFileHandler(logging.Handler):
    """Append log entries and refresh their external SHA-256 checksums."""

    def __init__(self, log_name: LogName, log_path: Path) -> None:
        """Prepare a protected log writer for one external file."""
        self.log_name = log_name
        self.log_path = log_path
        super().__init__()
        self.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    def emit(self, record: logging.LogRecord) -> None:
        """Write safely, restore read-only protection, and update its checksum."""
        with _integrity_lock:
            try:
                log_is_unchanged = log_matches_saved_checksum(
                    self.log_name,
                    self.log_path,
                )
            except OSError:
                add_logging_warning(self.log_name, self.log_path)
                self.handleError(record)
                return
            if not log_is_unchanged:
                add_integrity_warning(self.log_name, self.log_path)
                return
            try:
                set_log_file_read_only(self.log_path, False)
                with self.log_path.open("a", encoding="utf-8") as log_file:
                    log_file.write(f"{self.format(record)}\n")
                set_log_file_read_only(self.log_path, True)
                save_log_checksum(self.log_name, self.log_path)
            except (OSError, ValueError):
                add_logging_warning(self.log_name, self.log_path)
                self.handleError(record)


def log_application_activity(activity: str) -> None:
    """Record a normal application action in the application log."""
    logging.getLogger(LOGGER_NAME_BY_LOG["application_log"]).info(activity)


def log_application_error(
    location: str,
    cause: str,
    suggested_fix: str,
    error: BaseException | None = None,
) -> None:
    """Explain where an application error happened and how to fix it."""
    logger = logging.getLogger(LOGGER_NAME_BY_LOG["application_log"])
    error_message = (
        f"Where: {location}. What happened: {cause}. "
        f"How to fix it: {suggested_fix}"
    )
    if error is None:
        logger.error(error_message)
    else:
        error_details = "".join(
            traceback.format_exception(
                type(error),
                error,
                error.__traceback__,
            )
        )
        logger.error("%s Details: %s", error_message, error_details)


def log_api_communication(
    communication_type: str,
    requested: str,
    returned: str,
    http_status_code: int | None,
    correlation_id: str,
) -> None:
    """Record the request, full reply, status, and correlation ID as JSON."""
    communication_record = {
        "communication_type": communication_type,
        "requested": requested,
        "returned": returned,
        "http_status_code": http_status_code,
        "correlation_id": correlation_id,
    }
    logging.getLogger(
        LOGGER_NAME_BY_LOG["api_communications_log"]
    ).info(json.dumps(communication_record, ensure_ascii=False))


def log_test_results(full_results: str) -> None:
    """Store the complete printed output from an application test run."""
    logging.getLogger(LOGGER_NAME_BY_LOG["testing_log"]).info(
        "Full test run results follow:\n%s",
        full_results.rstrip(),
    )


def check_log_file_integrity(log_name: LogName, log_path: str) -> bool:
    """Check a selected log file against its saved SHA-256 checksum."""
    resolved_log_path = Path(log_path).expanduser().resolve()
    with _integrity_lock:
        if not resolved_log_path.exists():
            return True
        if not prepare_integrity_record(log_name, resolved_log_path):
            return False
        matches = log_matches_saved_checksum(log_name, resolved_log_path)
        if not matches:
            add_integrity_warning(log_name, resolved_log_path)
        return matches


def get_integrity_warnings() -> list[str]:
    """Return clear messages for log files that failed checksum checks."""
    return [*_integrity_warnings, *_logging_warnings]


def prepare_integrity_record(log_name: LogName, log_path: Path) -> bool:
    """Create a first checksum record or verify an existing one."""
    manifest = read_integrity_manifest()
    saved_checksum = manifest.get(get_manifest_key(log_name, log_path))
    if saved_checksum is None:
        if log_path.exists():
            checksum = calculate_file_checksum(log_path)
        else:
            log_path.touch()
            checksum = calculate_file_checksum(log_path)
        manifest[get_manifest_key(log_name, log_path)] = checksum
        write_integrity_manifest(manifest)
        set_log_file_read_only(log_path, True)
        return True
    if not log_path.exists():
        add_integrity_warning(log_name, log_path)
        return False
    if calculate_file_checksum(log_path) != saved_checksum:
        add_integrity_warning(log_name, log_path)
        return False
    set_log_file_read_only(log_path, True)
    return True


def log_matches_saved_checksum(log_name: LogName, log_path: Path) -> bool:
    """Compare current log bytes with the checksum kept outside the log."""
    manifest = read_integrity_manifest()
    saved_checksum = manifest.get(get_manifest_key(log_name, log_path))
    if saved_checksum is None or not log_path.exists():
        return False
    return calculate_file_checksum(log_path) == saved_checksum


def save_log_checksum(log_name: LogName, log_path: Path) -> None:
    """Update the separate checksum record after a successful log write."""
    manifest = read_integrity_manifest()
    manifest[get_manifest_key(log_name, log_path)] = calculate_file_checksum(
        log_path
    )
    write_integrity_manifest(manifest)


def calculate_file_checksum(log_path: Path) -> str:
    """Calculate SHA-256 for a log file without loading all of it into memory."""
    file_hasher = hashlib.sha256()
    with log_path.open("rb") as log_file:
        for file_piece in iter(lambda: log_file.read(64 * 1024), b""):
            file_hasher.update(file_piece)
    return file_hasher.hexdigest()


def set_log_file_read_only(log_path: Path, should_be_read_only: bool) -> None:
    """Protect saved logs from ordinary edits but allow the app to append."""
    if should_be_read_only:
        file_permissions = stat.S_IREAD
    else:
        file_permissions = stat.S_IREAD | stat.S_IWRITE
    os.chmod(log_path, file_permissions)


def get_manifest_key(log_name: LogName, log_path: Path) -> str:
    """Make a stable checksum name from a log type and its full path."""
    return f"{log_name}|{log_path}"


def read_integrity_manifest() -> dict[str, str]:
    """Read known checksums and clearly reject a damaged checksum file."""
    if not _integrity_manifest_path.exists():
        return {}
    try:
        manifest = json.loads(
            _integrity_manifest_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise OSError(
            "The log checksum file could not be read. Check that it has not "
            "been changed and that this account can read it."
        ) from error
    if not isinstance(manifest, dict) or not all(
        isinstance(name, str) and isinstance(checksum, str)
        for name, checksum in manifest.items()
    ):
        raise OSError(
            "The log checksum file has an unexpected format. Do not edit it."
        )
    return manifest


def write_integrity_manifest(manifest: dict[str, str]) -> None:
    """Save checksums atomically so a partial write is not mistaken as valid."""
    _integrity_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_manifest = _integrity_manifest_path.with_suffix(".tmp")
    temporary_manifest.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    temporary_manifest.replace(_integrity_manifest_path)


def add_integrity_warning(log_name: LogName, log_path: Path) -> None:
    """Remember a plain-English warning when a log fails its checksum check."""
    warning_message = (
        f"The {log_name.replace('_', ' ')} at {log_path} does not match its "
        "saved checksum. It may have been changed outside this program. "
        "Review the file and checksum settings before using it."
    )
    if warning_message not in _integrity_warnings:
        _integrity_warnings.append(warning_message)


def add_logging_warning(log_name: LogName, log_path: Path) -> None:
    """Remember when a log could not be written or protected."""
    warning_message = (
        f"The {log_name.replace('_', ' ')} at {log_path} could not be updated "
        "or made read-only. Check the file and folder permissions."
    )
    if warning_message not in _logging_warnings:
        _logging_warnings.append(warning_message)


def format_log_file(log_path: str, integrity_is_valid: bool) -> str:
    """Read a log for display and clearly label checksum failures."""
    resolved_log_path = Path(log_path).expanduser().resolve()
    if not resolved_log_path.exists():
        return "This log file has not been created yet."
    log_text = resolved_log_path.read_text(encoding="utf-8")
    if not integrity_is_valid:
        log_text = (
            "WARNING: This log file does not match its saved checksum and may "
            "have been changed outside the program.\n\n"
            + log_text
        )
    if not log_text:
        return "This log file is empty."
    return log_text
