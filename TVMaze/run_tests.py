"""Run the tests and save the same results that appear on the screen."""

from datetime import datetime
from pathlib import Path
import sys
from typing import TextIO
import unittest

from config import DEFAULT_TESTS_LOG_FILE, SettingsError, load_settings
from helpers import (
    ConsoleAndFileWriter,
    log_file_matches_saved_checksum,
    save_log_checksum,
)


PROGRAM_FOLDER = Path(__file__).resolve().parent
TESTS_FOLDER = PROGRAM_FOLDER / "tests"


def run_test_suite(
    tests_log_path: str | Path,
    tests_folder: str | Path = TESTS_FOLDER,
    screen: TextIO | None = None,
    startup_note: str | None = None,
) -> int:
    """Run every test, show its results, and save them in the tests log."""
    if screen is None:
        screen = sys.stdout

    log_file_path = Path(tests_log_path).expanduser()
    checksum_file_path = Path(f"{log_file_path}.sha256")
    log_file_existed = log_file_path.exists()
    earlier_log_is_trusted = not log_file_existed

    if log_file_existed:
        try:
            earlier_log_is_trusted = log_file_matches_saved_checksum(
                log_file_path,
                checksum_file_path,
            )
        except OSError:
            earlier_log_is_trusted = False

    try:
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = log_file_path.open("a", encoding="utf-8")
    except (OSError, ValueError) as error:
        if startup_note:
            screen.write(f"{startup_note}\n")
        screen.write(
            "The tests could not be saved to the tests log. "
            "The tests will still run and their results will appear below.\n"
            f"Log problem: {error}\n\n"
        )
        screen.flush()
        result = run_tests_on_screen(tests_folder, screen)
        return 0 if result.wasSuccessful() else 1

    output_writer: ConsoleAndFileWriter | None = None
    result: unittest.result.TestResult | None = None
    try:
        with log_file:
            output_writer = ConsoleAndFileWriter(screen, log_file)
            output_writer.writeln()
            output_writer.writeln("=" * 60)
            output_writer.writeln(
                "Test run started: "
                f"{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}"
            )
            if startup_note:
                output_writer.writeln(startup_note)
            if log_file_existed and not earlier_log_is_trusted:
                output_writer.writeln(
                    "The earlier tests log did not match its saved checksum. "
                    "The program will keep the old checksum so the change "
                    "remains visible."
                )

            result = run_tests_on_screen(tests_folder, output_writer)
            output_writer.flush()
    except OSError as error:
        screen.write(
            "The tests ran, but the tests log could not be fully written.\n"
            f"Log problem: {error}\n"
        )
        screen.flush()
        return 0 if result is not None and result.wasSuccessful() else 1

    if result is None:
        screen.write("The test runner stopped before it could finish.\n")
        screen.flush()
        return 1
    if output_writer is not None and output_writer.log_problem is not None:
        screen.write(
            "The tests ran, but the tests log could not be fully written.\n"
            f"Log problem: {output_writer.log_problem}\n"
        )
        screen.flush()
        return 0 if result.wasSuccessful() else 1

    if earlier_log_is_trusted:
        try:
            save_log_checksum(log_file_path, checksum_file_path)
        except OSError as error:
            screen.write(
                "The tests ran and were saved, but the tests log checksum "
                "could not be updated.\n"
                f"Checksum problem: {error}\n"
            )
            screen.flush()

    return 0 if result.wasSuccessful() else 1


def run_tests_on_screen(
    tests_folder: str | Path,
    screen: TextIO,
) -> unittest.result.TestResult:
    """Discover the test files, run them, and send the results to the screen."""
    test_suite = unittest.defaultTestLoader.discover(str(tests_folder))
    test_runner = unittest.TextTestRunner(stream=screen, verbosity=2)
    return test_runner.run(test_suite)


def main() -> int:
    """Use the saved tests log location and explain problems reading settings."""
    try:
        settings = load_settings()
    except SettingsError as error:
        return run_test_suite(
            DEFAULT_TESTS_LOG_FILE,
            startup_note=(
                "Saved settings could not be read, so the tests log is using "
                f"its default location. Details: {error}"
            ),
        )

    return run_test_suite(settings.tests_log_path)


if __name__ == "__main__":
    raise SystemExit(main())
