"""Check that API connection notes are clear and useful."""

from email.message import Message
import logging
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from activity_log import ACTIVITY_LOGGER_NAME, start_activity_log, stop_activity_log
from tvmaze_api import request_tvmaze


class FakeWebResponse:
    """Act like a tiny reply from a website."""

    status = 200
    headers = {
        "content-type": "application/json",
        "content-length": "12",
        "x-request-id": "server-request-123",
        "set-cookie": "private-cookie-value",
    }

    def __enter__(self) -> "FakeWebResponse":
        """Return this pretend reply when a request starts."""
        return self

    def __exit__(self, *arguments: object) -> None:
        """Allow the pretend reply to be used in a with statement."""
        del arguments

    def read(self) -> bytes:
        """Return a pretend response body."""
        return b'{"name":"Hi"}'


class ActivityLogTests(unittest.TestCase):
    """Check the details written when a web request is made."""

    def setUp(self) -> None:
        """Create a temporary file for this test's activity notes."""
        self.temporary_folder = tempfile.TemporaryDirectory()
        self.log_file = Path(self.temporary_folder.name) / "activity.log"
        start_activity_log(self.log_file)

    def tearDown(self) -> None:
        """Close the activity log and remove the temporary test folder."""
        stop_activity_log()
        self.temporary_folder.cleanup()

    def read_activity_notes(self) -> str:
        """Read all the notes written during this test."""
        for file_handler in logging.getLogger(ACTIVITY_LOGGER_NAME).handlers:
            file_handler.flush()
        return self.log_file.read_text(encoding="utf-8")

    def test_successful_request_logs_status_and_server_request_id(self) -> None:
        """A successful request should log its status and useful reply headers."""
        with patch("tvmaze_api.urlopen", return_value=FakeWebResponse()):
            response_body = request_tvmaze(
                "https://api.tvmaze.com/shows?q=Example",
                "program details",
                10,
                "search-correlation-123",
            )

        notes = self.read_activity_notes()
        self.assertEqual(response_body, b'{"name":"Hi"}')
        self.assertIn("search-correlation-123", notes)
        self.assertIn("HTTP status 200", notes)
        self.assertIn("server-request-123", notes)
        self.assertIn("content-type: application/json", notes)
        self.assertNotIn("private-cookie-value", notes)

    def test_http_problem_logs_status_and_trace_headers(self) -> None:
        """An HTTP error should include its status and server trace details."""
        reply_headers = Message()
        reply_headers["X-Request-ID"] = "server-error-456"
        reply_headers["Set-Cookie"] = "private-cookie-value"
        http_problem = HTTPError(
            "https://api.tvmaze.com/shows?q=Example",
            503,
            "Service Unavailable",
            reply_headers,
            None,
        )

        with patch("tvmaze_api.urlopen", side_effect=http_problem):
            with self.assertRaises(HTTPError):
                request_tvmaze(
                    "https://api.tvmaze.com/shows?q=Example",
                    "program details",
                    10,
                    "search-correlation-456",
                )

        notes = self.read_activity_notes()
        self.assertIn("HTTP status 503", notes)
        self.assertIn("server-error-456", notes)
        self.assertNotIn("private-cookie-value", notes)

    def test_connection_problem_logs_the_error(self) -> None:
        """A failed network connection should include its reason in the log."""
        with patch(
            "tvmaze_api.urlopen",
            side_effect=OSError("Network is unreachable"),
        ):
            with self.assertRaises(OSError):
                request_tvmaze(
                    "https://api.tvmaze.com/shows?q=Example",
                    "program details",
                    10,
                    "search-correlation-789",
                )

        notes = self.read_activity_notes()
        self.assertIn("search-correlation-789", notes)
        self.assertIn("OSError", notes)
        self.assertIn("Network is unreachable", notes)


if __name__ == "__main__":
    unittest.main()
