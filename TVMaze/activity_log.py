"""Write a plain-English record of requests made to TVMaze."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import time
from collections.abc import Mapping
from uuid import uuid4

from helpers import close_logger_handlers, make_one_line


ACTIVITY_LOGGER_NAME = "tvmaze_activity"
MAX_ACTIVITY_LOG_SIZE_BYTES = 1_000_000
NUMBER_OF_OLD_LOG_FILES_TO_KEEP = 3

HELPFUL_REPLY_HEADERS = (
    "x-request-id",
    "x-correlation-id",
    "traceparent",
    "cf-ray",
    "x-amzn-requestid",
    "x-amz-cf-id",
    "server",
    "date",
    "content-type",
    "content-length",
    "retry-after",
    "via",
)


def start_activity_log(log_file_path: str | Path) -> None:
    """Start saving readable activity notes at the chosen location."""
    activity_log_file = Path(log_file_path).expanduser()
    activity_logger = logging.getLogger(ACTIVITY_LOGGER_NAME)
    activity_logger.setLevel(logging.INFO)
    activity_logger.propagate = False

    activity_log_file.parent.mkdir(parents=True, exist_ok=True)
    log_format = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        activity_log_file,
        maxBytes=MAX_ACTIVITY_LOG_SIZE_BYTES,
        backupCount=NUMBER_OF_OLD_LOG_FILES_TO_KEEP,
        encoding="utf-8",
    )
    file_handler.setFormatter(log_format)
    close_logger_handlers(activity_logger)
    activity_logger.addHandler(file_handler)
    activity_logger.info("The TVMaze activity log has started.")
    activity_logger.info("Activity notes are saved in: %s", activity_log_file)


def stop_activity_log() -> None:
    """Close the log file cleanly when the program exits."""
    activity_logger = logging.getLogger(ACTIVITY_LOGGER_NAME)
    close_logger_handlers(activity_logger)


def make_search_reference() -> str:
    """Make a unique label that connects the notes for one search."""
    return str(uuid4())


def log_request_start(
    search_reference: str,
    request_part_name: str,
    request_url: str,
    timeout_seconds: int,
) -> float:
    """Record a request before it leaves the computer and start its timer."""
    logging.getLogger(ACTIVITY_LOGGER_NAME).info(
        "Search %s: starting the %s request. Method: GET. Address: %s. "
        "Wait limit: %s seconds.",
        search_reference,
        make_one_line(request_part_name),
        make_one_line(request_url),
        timeout_seconds,
    )
    return time.monotonic()


def log_request_success(
    search_reference: str,
    request_part_name: str,
    request_url: str,
    response_status_code: int,
    response_headers: Mapping[str, str],
    elapsed_seconds: float,
    reply_size_bytes: int,
) -> None:
    """Record the reply status, safe diagnostic headers, size, and wait time."""
    header_notes = make_helpful_header_text(response_headers)
    logging.getLogger(ACTIVITY_LOGGER_NAME).info(
        "Search %s: the %s request received HTTP status %s from %s. "
        "It took %.3f seconds and returned %s bytes.%s",
        search_reference,
        make_one_line(request_part_name),
        response_status_code,
        make_one_line(request_url),
        elapsed_seconds,
        reply_size_bytes,
        f" Reply details: {header_notes}" if header_notes else "",
    )


def log_http_error(
    search_reference: str,
    request_part_name: str,
    request_url: str,
    response_status_code: int,
    response_headers: Mapping[str, str],
    elapsed_seconds: float,
    problem: str,
) -> None:
    """Record an HTTP error and the safe response details that may explain it."""
    header_notes = make_helpful_header_text(response_headers)
    logging.getLogger(ACTIVITY_LOGGER_NAME).warning(
        "Search %s: the %s request received HTTP status %s from %s after "
        "%.3f seconds. The server said: %s.%s",
        search_reference,
        make_one_line(request_part_name),
        response_status_code,
        make_one_line(request_url),
        elapsed_seconds,
        make_one_line(problem),
        f" Reply details: {header_notes}" if header_notes else "",
    )


def log_connection_error(
    search_reference: str,
    request_part_name: str,
    request_url: str,
    elapsed_seconds: float,
    problem: BaseException,
) -> None:
    """Record why a request could not connect or finish."""
    logging.getLogger(ACTIVITY_LOGGER_NAME).error(
        "Search %s: the %s request to %s did not finish after %.3f seconds. "
        "Problem type: %s. Details: %s.",
        search_reference,
        make_one_line(request_part_name),
        make_one_line(request_url),
        elapsed_seconds,
        type(problem).__name__,
        make_one_line(explain_connection_problem(problem)),
    )


def log_unreadable_reply(
    search_reference: str,
    request_part_name: str,
    request_url: str,
    problem: str,
) -> None:
    """Record when a successful web reply cannot be understood by the app."""
    logging.getLogger(ACTIVITY_LOGGER_NAME).error(
        "Search %s: the %s request to %s returned a reply that the app "
        "could not read. Details: %s.",
        search_reference,
        make_one_line(request_part_name),
        make_one_line(request_url),
        make_one_line(problem),
    )


def make_helpful_header_text(headers: Mapping[str, str]) -> str:
    """Keep only helpful server details and leave private headers out."""
    safe_details = []
    for header_name in HELPFUL_REPLY_HEADERS:
        header_value = headers.get(header_name)
        if header_value:
            safe_details.append(
                f"{header_name}: {make_one_line(header_value, 300)}"
            )

    return "; ".join(safe_details)


def explain_connection_problem(problem: BaseException) -> str:
    """Turn common connection errors into short, useful explanations."""
    reason = getattr(problem, "reason", None)
    if reason is not None:
        return f"{type(reason).__name__}: {reason}"
    return str(problem) or "No extra error details were provided."
