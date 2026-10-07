"""Record TVMaze API request and reply details to help find API problems."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import time
from collections.abc import Mapping
from uuid import uuid4

from helpers import close_logger_handlers, make_one_line


API_ACTIVITY_LOGGER_NAME = "tvmaze_api_activity"
MAX_API_ACTIVITY_LOG_SIZE_BYTES = 1_000_000
NUMBER_OF_OLD_API_LOG_FILES_TO_KEEP = 3

HELPFUL_API_REPLY_HEADERS = (
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


def start_api_activity_logging(log_file_path: str | Path) -> None:
    """Start the file that records TVMaze API activity for troubleshooting."""
    api_activity_log_file = Path(log_file_path).expanduser()
    api_activity_logger = logging.getLogger(API_ACTIVITY_LOGGER_NAME)
    api_activity_logger.setLevel(logging.INFO)
    api_activity_logger.propagate = False

    api_activity_log_file.parent.mkdir(parents=True, exist_ok=True)
    log_format = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        api_activity_log_file,
        maxBytes=MAX_API_ACTIVITY_LOG_SIZE_BYTES,
        backupCount=NUMBER_OF_OLD_API_LOG_FILES_TO_KEEP,
        encoding="utf-8",
    )
    file_handler.setFormatter(log_format)
    close_logger_handlers(api_activity_logger)
    api_activity_logger.addHandler(file_handler)
    api_activity_logger.info("TVMaze API issue tracking has started.")
    api_activity_logger.info(
        "API troubleshooting details are saved in: %s",
        api_activity_log_file,
    )


def stop_api_activity_logging() -> None:
    """Close the API troubleshooting log cleanly when the program exits."""
    api_activity_logger = logging.getLogger(API_ACTIVITY_LOGGER_NAME)
    close_logger_handlers(api_activity_logger)


def make_api_search_reference() -> str:
    """Make a unique label that connects the API notes for one search."""
    return str(uuid4())


def log_api_request_start(
    search_reference: str,
    request_part_name: str,
    request_url: str,
    timeout_seconds: int,
) -> float:
    """Record an API request before it leaves the computer and start its timer."""
    logging.getLogger(API_ACTIVITY_LOGGER_NAME).info(
        "API search %s: starting the %s request. Method: GET. Address: %s. "
        "Wait limit: %s seconds.",
        search_reference,
        make_one_line(request_part_name),
        make_one_line(request_url),
        timeout_seconds,
    )
    return time.monotonic()


def log_successful_api_reply(
    search_reference: str,
    request_part_name: str,
    request_url: str,
    response_status_code: int,
    response_headers: Mapping[str, str],
    elapsed_seconds: float,
    reply_size_bytes: int,
) -> None:
    """Record the API reply status, safe headers, size, and wait time."""
    header_notes = make_helpful_api_header_text(response_headers)
    logging.getLogger(API_ACTIVITY_LOGGER_NAME).info(
        "API search %s: the %s request received HTTP status %s from %s. "
        "It took %.3f seconds and returned %s bytes.%s",
        search_reference,
        make_one_line(request_part_name),
        response_status_code,
        make_one_line(request_url),
        elapsed_seconds,
        reply_size_bytes,
        f" Reply details: {header_notes}" if header_notes else "",
    )


def log_api_http_error(
    search_reference: str,
    request_part_name: str,
    request_url: str,
    response_status_code: int,
    response_headers: Mapping[str, str],
    elapsed_seconds: float,
    problem: str,
) -> None:
    """Record an API HTTP error and useful reply details that may explain it."""
    header_notes = make_helpful_api_header_text(response_headers)
    logging.getLogger(API_ACTIVITY_LOGGER_NAME).warning(
        "API search %s: the %s request received HTTP status %s from %s after "
        "%.3f seconds. The server said: %s.%s",
        search_reference,
        make_one_line(request_part_name),
        response_status_code,
        make_one_line(request_url),
        elapsed_seconds,
        make_one_line(problem),
        f" Reply details: {header_notes}" if header_notes else "",
    )


def log_api_connection_error(
    search_reference: str,
    request_part_name: str,
    request_url: str,
    elapsed_seconds: float,
    problem: BaseException,
) -> None:
    """Record why an API request could not connect or finish."""
    logging.getLogger(API_ACTIVITY_LOGGER_NAME).error(
        "API search %s: the %s request to %s did not finish after %.3f seconds. "
        "Problem type: %s. Details: %s.",
        search_reference,
        make_one_line(request_part_name),
        make_one_line(request_url),
        elapsed_seconds,
        type(problem).__name__,
        make_one_line(explain_api_connection_problem(problem)),
    )


def log_unreadable_api_reply(
    search_reference: str,
    request_part_name: str,
    request_url: str,
    problem: str,
) -> None:
    """Record when an API reply cannot be understood by the app."""
    logging.getLogger(API_ACTIVITY_LOGGER_NAME).error(
        "API search %s: the %s request to %s returned a reply that the app "
        "could not read. Details: %s.",
        search_reference,
        make_one_line(request_part_name),
        make_one_line(request_url),
        make_one_line(problem),
    )


def make_helpful_api_header_text(headers: Mapping[str, str]) -> str:
    """Keep useful API server details and leave private headers out."""
    safe_details = []
    for header_name in HELPFUL_API_REPLY_HEADERS:
        header_value = headers.get(header_name)
        if header_value:
            safe_details.append(
                f"{header_name}: {make_one_line(header_value, 300)}"
            )

    return "; ".join(safe_details)


def explain_api_connection_problem(problem: BaseException) -> str:
    """Turn common API connection errors into short, useful explanations."""
    reason = getattr(problem, "reason", None)
    if reason is not None:
        return f"{type(reason).__name__}: {reason}"
    return str(problem) or "No extra error details were provided."
