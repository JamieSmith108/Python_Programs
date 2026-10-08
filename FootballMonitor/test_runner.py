"""Run the app's unit tests and store their full output in the testing log."""

from io import StringIO
from pathlib import Path
import unittest

from logging_service import log_test_results


def run_all_tests() -> tuple[bool, str]:
    """Run every project test and save the full results for later viewing."""
    tests_folder = Path(__file__).resolve().parent / "tests"
    try:
        test_suite = unittest.defaultTestLoader.discover(str(tests_folder))
    except (ImportError, OSError) as error:
        full_results = (
            "The test runner could not find or load the project tests.\n"
            f"Cause: {type(error).__name__}: {error}\n"
            "How to fix it: Check that the tests folder and its Python files "
            "are present and readable."
        )
        log_test_results(full_results)
        return False, full_results

    result_stream = StringIO()
    test_result = unittest.TextTestRunner(
        stream=result_stream,
        verbosity=2,
    ).run(test_suite)
    full_results = result_stream.getvalue()
    log_test_results(full_results)
    return test_result.wasSuccessful(), full_results
