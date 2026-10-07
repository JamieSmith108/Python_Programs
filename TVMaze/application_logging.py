"""Record problems that happen inside the TVMaze Show Finder program."""

import logging
from pathlib import Path

from helpers import start_rotating_file_log, stop_rotating_file_log


APPLICATION_LOGGER_NAME = "tvmaze_application"


def start_application_logging(log_file_path: str | Path) -> None:
    """Start the file that records errors inside the application."""
    start_rotating_file_log(
        APPLICATION_LOGGER_NAME,
        log_file_path,
        "TVMaze Show Finder application issue tracking has started.",
        "Application problem details are saved in:",
    )


def stop_application_logging() -> None:
    """Close the application log file cleanly when the program exits."""
    stop_rotating_file_log(APPLICATION_LOGGER_NAME)


def log_application_error(action: str, problem: BaseException) -> None:
    """Save an application error, its cause, and its place in the code."""
    logging.getLogger(APPLICATION_LOGGER_NAME).error(
        "The application had a problem while %s. Error type: %s. Details: %s.",
        action,
        type(problem).__name__,
        problem,
        exc_info=(type(problem), problem, problem.__traceback__),
    )


def log_application_issue(issue_description: str) -> None:
    """Save a useful note about an application problem without an exception."""
    logging.getLogger(APPLICATION_LOGGER_NAME).warning(
        "Application issue: %s",
        issue_description,
    )
