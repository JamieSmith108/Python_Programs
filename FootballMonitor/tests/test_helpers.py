"""Check that shared ESPN request helpers reject unsafe replies."""

from email.message import Message
import json
import unittest
from unittest.mock import patch

from helpers import FootballDataError, get_espn_json


class FakeJsonResponse:
    """Pretend to be a small successful ESPN JSON response."""

    status = 200

    def __init__(self, reply: object) -> None:
        """Prepare a realistic JSON response for a request test."""
        self.headers = Message()
        self.headers["Content-Type"] = "application/json; charset=utf-8"
        self.reply_bytes = json.dumps(reply).encode("utf-8")

    def __enter__(self) -> "FakeJsonResponse":
        """Return this reply when the request opens it."""
        return self

    def __exit__(self, *arguments: object) -> None:
        """Allow this reply to be opened with a with statement."""
        del arguments

    def read(self, size: int = -1) -> bytes:
        """Return only the number of bytes the request asked to read."""
        return self.reply_bytes if size < 0 else self.reply_bytes[:size]


class FootballHelperTests(unittest.TestCase):
    """Check the network helper accepts safe JSON and rejects unsafe inputs."""

    def test_safe_espn_address_returns_json(self) -> None:
        """A reply from ESPN's secure API should be returned as a dictionary."""
        fake_response = FakeJsonResponse({"events": []})
        with patch("helpers.build_opener") as build_safe_opener:
            build_safe_opener.return_value.open.return_value = fake_response

            reply = get_espn_json(
                "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard"
            )

        self.assertEqual(reply, {"events": []})

    def test_untrusted_website_is_rejected_without_a_connection(self) -> None:
        """The helper must not open a website other than ESPN's approved host."""
        with patch("helpers.build_opener") as build_safe_opener:
            with self.assertRaisesRegex(FootballDataError, "not ESPN's approved"):
                get_espn_json("https://evil.example/football")

        build_safe_opener.assert_not_called()

    def test_web_page_instead_of_json_is_rejected(self) -> None:
        """A website page must not be mistaken for football data."""
        fake_response = FakeJsonResponse({"events": []})
        fake_response.headers.replace_header("Content-Type", "text/html")
        with patch("helpers.build_opener") as build_safe_opener:
            build_safe_opener.return_value.open.return_value = fake_response

            with self.assertRaisesRegex(FootballDataError, "format"):
                get_espn_json(
                    "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard"
                )

    def test_invalid_json_is_explained(self) -> None:
        """Unreadable ESPN text should become a clear data error."""
        fake_response = FakeJsonResponse({})
        fake_response.reply_bytes = b"\xff"
        with patch("helpers.build_opener") as build_safe_opener:
            build_safe_opener.return_value.open.return_value = fake_response

            with self.assertRaisesRegex(FootballDataError, "could not understand"):
                get_espn_json(
                    "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard"
                )


if __name__ == "__main__":
    unittest.main()
