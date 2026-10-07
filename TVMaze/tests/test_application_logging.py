"""Check that application problems are written to their own log file."""

from pathlib import Path
import tempfile
import unittest

from application_logging import (
    APPLICATION_LOGGER_NAME,
    log_application_error,
    log_application_issue,
    start_application_logging,
    stop_application_logging,
)
from helpers import read_log_file


class ApplicationLoggingTests(unittest.TestCase):
    """Check that application errors are saved with useful explanations."""

    def setUp(self) -> None:
        """Create a temporary application log file for this test."""
        self.temporary_folder = tempfile.TemporaryDirectory()
        self.log_file = Path(self.temporary_folder.name) / "application_log"
        start_application_logging(self.log_file)

    def tearDown(self) -> None:
        """Close the application log and remove the temporary folder."""
        stop_application_logging()
        self.temporary_folder.cleanup()

    def read_application_log(self) -> str:
        """Flush the log file and return all saved application notes."""
        return read_log_file(APPLICATION_LOGGER_NAME, self.log_file)

    def test_application_error_saves_the_explanation_and_code_location(self) -> None:
        """An application error should include its type, details, and traceback."""
        try:
            raise ValueError("The test setting was not a number.")
        except ValueError as error:
            log_application_error("reading a test setting", error)

        application_notes = self.read_application_log()

        self.assertIn("reading a test setting", application_notes)
        self.assertIn("ValueError", application_notes)
        self.assertIn("The test setting was not a number.", application_notes)
        self.assertIn("Traceback (most recent call last)", application_notes)

    def test_application_issue_saves_a_plain_english_note(self) -> None:
        """A non-exception application issue should also be recorded."""
        log_application_issue("The settings form needs a whole number.")

        application_notes = self.read_application_log()

        self.assertIn("Application issue", application_notes)
        self.assertIn("The settings form needs a whole number.", application_notes)

    def test_application_log_is_created_in_a_new_folder(self) -> None:
        """The application logger should make missing parent folders."""
        another_log = Path(self.temporary_folder.name) / "new folder" / "application_log"

        start_application_logging(another_log)

        self.assertTrue(another_log.is_file())


if __name__ == "__main__":
    unittest.main()
