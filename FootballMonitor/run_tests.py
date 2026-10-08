"""Run the project tests and save their full results to the testing log."""

import sys

from log_settings import SettingsError, load_log_settings
from logging_service import (
    configure_log_files,
    log_application_activity,
    log_application_error,
)
from test_runner import run_all_tests


def main() -> int:
    """Configure external logs, run the tests, print their output, and return status."""
    try:
        configure_log_files(load_log_settings())
        log_application_activity("The command-line test runner started.")
        tests_passed, full_results = run_all_tests()
    except (ImportError, OSError, RuntimeError, SettingsError, ValueError) as error:
        print(
            "The tests could not run because the log settings or log files "
            f"could not be prepared: {error}",
            file=sys.stderr,
        )
        log_application_error(
            "starting the command-line test run",
            str(error),
            "Check the external log settings and file permissions, then try again.",
            error,
        )
        return 2

    print(full_results, end="")
    log_application_activity(
        f"The command-line test runner finished. Passed: {tests_passed}."
    )
    return 0 if tests_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
