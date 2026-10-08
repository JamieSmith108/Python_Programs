"""Check that API troubleshooting details are recorded clearly and safely."""

from email.message import Message
from http.client import IncompleteRead
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from api_activity_logging import (
    API_ACTIVITY_LOGGER_NAME,
    start_api_activity_logging,
    stop_api_activity_logging,
)
from helpers import read_log_file
from tvmaze_api import TVMazeError, request_tvmaze


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

    def read(self, size: int = -1) -> bytes:
        """Return a pretend response body."""
        del size
        return b'{"name":"Hi"}'


class UnexpectedContentResponse(FakeWebResponse):
    """Pretend that a website sent a web page instead of show information."""

    headers = {"content-type": "text/html"}


class OversizedContentResponse(FakeWebResponse):
    """Pretend that a website sent a reply larger than the safety limit."""

    def read(self, size: int = -1) -> bytes:
        """Return one byte more than the requested maximum."""
        return b"x" * (size + 1)


class APIActivityLoggingTests(unittest.TestCase):
    """Check the API details written to help find connection problems."""

    def setUp(self) -> None:
        """Create a temporary file for this test's API troubleshooting notes."""
        self.temporary_folder = tempfile.TemporaryDirectory()
        self.log_file = Path(self.temporary_folder.name) / "API_activity_logging.log"
        start_api_activity_logging(self.log_file)

    def tearDown(self) -> None:
        """Close the API log and remove the temporary test folder."""
        stop_api_activity_logging()
        self.temporary_folder.cleanup()

    def read_activity_notes(self) -> str:
        """Read all API troubleshooting notes written during this test."""
        return read_log_file(API_ACTIVITY_LOGGER_NAME, self.log_file)

    def test_successful_request_logs_status_and_server_request_id(self) -> None:
        """A successful request should log its status and useful reply headers."""
        with patch(
            "tvmaze_api.open_trusted_tvmaze_request",
            return_value=FakeWebResponse(),
        ):
            response_body = request_tvmaze(
                "https://api.tvmaze.com/singlesearch/shows?q=Example",
                "program details",
                10,
                "search-reference-123",
            )

        notes = self.read_activity_notes()
        self.assertEqual(response_body, b'{"name":"Hi"}')
        self.assertIn("API search", notes)
        self.assertIn("search-reference-123", notes)
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
            "https://api.tvmaze.com/singlesearch/shows?q=Example",
            503,
            "Service Unavailable",
            reply_headers,
            None,
        )

        with patch(
            "tvmaze_api.open_trusted_tvmaze_request",
            side_effect=http_problem,
        ):
            with self.assertRaises(HTTPError):
                request_tvmaze(
                    "https://api.tvmaze.com/singlesearch/shows?q=Example",
                    "program details",
                    10,
                    "search-reference-456",
                )

        notes = self.read_activity_notes()
        self.assertIn("HTTP status 503", notes)
        self.assertIn("server-error-456", notes)
        self.assertNotIn("private-cookie-value", notes)

    def test_connection_problem_logs_the_error(self) -> None:
        """A failed network connection should include its reason in the log."""
        with patch(
            "tvmaze_api.open_trusted_tvmaze_request",
            side_effect=OSError("Network is unreachable"),
        ):
            with self.assertRaises(OSError):
                request_tvmaze(
                    "https://api.tvmaze.com/singlesearch/shows?q=Example",
                    "program details",
                    10,
                    "search-reference-789",
                )

        notes = self.read_activity_notes()
        self.assertIn("search-reference-789", notes)
        self.assertIn("OSError", notes)
        self.assertIn("Network is unreachable", notes)

    def test_incomplete_http_reply_is_logged_as_an_api_connection_problem(self) -> None:
        """A reply cut short by the server should be recorded in the API log."""
        with patch(
            "tvmaze_api.open_trusted_tvmaze_request",
            side_effect=IncompleteRead(b'{"name":', 4),
        ):
            with self.assertRaises(IncompleteRead):
                request_tvmaze(
                    "https://api.tvmaze.com/singlesearch/shows?q=Example",
                    "program details",
                    10,
                    "incomplete-reply-reference",
                )

        notes = self.read_activity_notes()
        self.assertIn("incomplete-reply-reference", notes)
        self.assertIn("IncompleteRead", notes)

    def test_request_to_an_unapproved_website_is_stopped(self) -> None:
        """A request must be rejected before a connection is opened."""
        with patch(
            "tvmaze_api.open_trusted_tvmaze_request"
        ) as open_web_request:
            with self.assertRaisesRegex(TVMazeError, "not an approved"):
                request_tvmaze(
                    "https://evil.example/collect",
                    "program details",
                    10,
                    "unsafe-search-reference",
                )

        open_web_request.assert_not_called()

    def test_unexpected_reply_type_is_rejected_and_logged(self) -> None:
        """A web page must not be mistaken for the API's JSON answer."""
        with patch(
            "tvmaze_api.open_trusted_tvmaze_request",
            return_value=UnexpectedContentResponse(),
        ):
            with self.assertRaisesRegex(TVMazeError, "unexpected format"):
                request_tvmaze(
                    "https://api.tvmaze.com/singlesearch/shows?q=Example",
                    "program details",
                    10,
                    "unexpected-type-reference",
                )

        self.assertIn("unexpected type of information", self.read_activity_notes())

    def test_reply_larger_than_safety_limit_is_rejected_and_logged(self) -> None:
        """An oversized reply must not be read or used without a size limit."""
        with patch(
            "tvmaze_api.open_trusted_tvmaze_request",
            return_value=OversizedContentResponse(),
        ):
            with self.assertRaisesRegex(TVMazeError, "too large"):
                request_tvmaze(
                    "https://api.tvmaze.com/singlesearch/shows?q=Example",
                    "program details",
                    10,
                    "oversized-reply-reference",
                )

        self.assertIn("larger than the allowed", self.read_activity_notes())

    def test_api_log_is_created_at_the_chosen_location(self) -> None:
        """The API logger should create folders and a file at the chosen path."""
        other_log = (
            Path(self.temporary_folder.name)
            / "new folder"
            / "API_activity_logging.log"
        )

        start_api_activity_logging(str(other_log))

        self.assertTrue(other_log.is_file())
        self.assertTrue(self.log_file.is_file())


if __name__ == "__main__":
    unittest.main()
