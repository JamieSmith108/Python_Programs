"""Write a plain-English record of requests made to TVMaze."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import time
from collections.abc import Mapping
from uuid import uuid4

from config import ACTIVITY_LOG_FILE
from helpers import close_logger_handlers, make_one_line


ACTIVITY_LOGGER_NAME = "tvmaze_activity"
MAX_LOG_FILE_BYTES = 1_000_000
OLD_LOG_FILE_COUNT = 3

DIAGNOSTIC_HEADERS = (
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


def start_activity_log(log_file: Path = ACTIVITY_LOG_FILE) -> None:
    """Start saving readable activity notes in a rotating log file."""
    activity_logger = logging.getLogger(ACTIVITY_LOGGER_NAME)
    activity_logger.setLevel(logging.INFO)
    activity_logger.propagate = False
    close_logger_handlers(activity_logger)

    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_format = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=MAX_LOG_FILE_BYTES,
        backupCount=OLD_LOG_FILE_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(log_format)
    activity_logger.addHandler(file_handler)
    activity_logger.info("The TVMaze activity log has started.")
    activity_logger.info("Activity notes are saved in: %s", log_file)


def stop_activity_log() -> None:
    """Close the log file cleanly when the program exits."""
    activity_logger = logging.getLogger(ACTIVITY_LOGGER_NAME)
    close_logger_handlers(activity_logger)


def make_correlation_id() -> str:
    """Make a unique label that connects the notes for one search."""
    return str(uuid4())


def note_request_started(
    correlation_id: str,
    request_name: str,
    request_url: str,
    timeout_seconds: int,
) -> float:
    """Record a request before it leaves the computer and start its timer."""
    logging.getLogger(ACTIVITY_LOGGER_NAME).info(
        "Search %s: starting the %s request. Method: GET. Address: %s. "
        "Wait limit: %s seconds.",
        correlation_id,
        make_one_line(request_name),
        make_one_line(request_url),
        timeout_seconds,
    )
    return time.monotonic()


def note_response_received(
    correlation_id: str,
    request_name: str,
    request_url: str,
    http_status: int,
    response_headers: Mapping[str, str],
    elapsed_seconds: float,
    response_size: int,
) -> None:
    """Record the reply status, safe diagnostic headers, size, and wait time."""
    header_notes = describe_diagnostic_headers(response_headers)
    logging.getLogger(ACTIVITY_LOGGER_NAME).info(
        "Search %s: the %s request received HTTP status %s from %s. "
        "It took %.3f seconds and returned %s bytes.%s",
        correlation_id,
        make_one_line(request_name),
        http_status,
        make_one_line(request_url),
        elapsed_seconds,
        response_size,
        f" Reply details: {header_notes}" if header_notes else "",
    )


def note_http_problem(
    correlation_id: str,
    request_name: str,
    request_url: str,
    http_status: int,
    response_headers: Mapping[str, str],
    elapsed_seconds: float,
    problem: str,
) -> None:
    """Record an HTTP error and the safe response details that may explain it."""
    header_notes = describe_diagnostic_headers(response_headers)
    logging.getLogger(ACTIVITY_LOGGER_NAME).warning(
        "Search %s: the %s request received HTTP status %s from %s after "
        "%.3f seconds. The server said: %s.%s",
        correlation_id,
        make_one_line(request_name),
        http_status,
        make_one_line(request_url),
        elapsed_seconds,
        make_one_line(problem),
        f" Reply details: {header_notes}" if header_notes else "",
    )


def note_connection_problem(
    correlation_id: str,
    request_name: str,
    request_url: str,
    elapsed_seconds: float,
    problem: BaseException,
) -> None:
    """Record why a request could not connect or finish."""
    logging.getLogger(ACTIVITY_LOGGER_NAME).error(
        "Search %s: the %s request to %s did not finish after %.3f seconds. "
        "Problem type: %s. Details: %s.",
        correlation_id,
        make_one_line(request_name),
        make_one_line(request_url),
        elapsed_seconds,
        type(problem).__name__,
        make_one_line(describe_connection_problem(problem)),
    )


def note_unreadable_reply(
    correlation_id: str,
    request_name: str,
    request_url: str,
    problem: str,
) -> None:
    """Record when a successful web reply cannot be understood by the app."""
    logging.getLogger(ACTIVITY_LOGGER_NAME).error(
        "Search %s: the %s request to %s returned a reply that the app "
        "could not read. Details: %s.",
        correlation_id,
        make_one_line(request_name),
        make_one_line(request_url),
        make_one_line(problem),
    )


def describe_diagnostic_headers(headers: Mapping[str, str]) -> str:
    """Keep only helpful server details and leave private headers out."""
    safe_details = []
    for header_name in DIAGNOSTIC_HEADERS:
        header_value = headers.get(header_name)
        if header_value:
            safe_details.append(
                f"{header_name}: {make_one_line(header_value, 300)}"
            )

    return "; ".join(safe_details)


def describe_connection_problem(problem: BaseException) -> str:
    """Turn common connection errors into short, useful explanations."""
    reason = getattr(problem, "reason", None)
    if reason is not None:
        return f"{type(reason).__name__}: {reason}"
    return str(problem) or "No extra error details were provided."
