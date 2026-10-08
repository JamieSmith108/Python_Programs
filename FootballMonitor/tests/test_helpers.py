"""Check that shared ESPN request helpers reject unsafe replies."""

from email.message import Message
from io import BytesIO
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from helpers import FootballDataError, get_espn_image, get_espn_json


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
        with (
            patch("helpers.build_opener") as build_safe_opener,
            patch("helpers.log_api_communication") as log_communication,
        ):
            build_safe_opener.return_value.open.return_value = fake_response

            reply = get_espn_json(
                "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard"
            )

        self.assertEqual(reply, {"events": []})
        logged_values = log_communication.call_args.args
        self.assertEqual(logged_values[0], "GET")
        self.assertIn("/scoreboard", logged_values[1])
        self.assertEqual(logged_values[2], '{"events": []}')
        self.assertEqual(logged_values[3], 200)
        self.assertTrue(logged_values[4])

    def test_json_suffix_content_type_is_accepted(self) -> None:
        """ESPN JSON types such as application/ld+json must be accepted."""
        fake_response = FakeJsonResponse({"sports": []})
        fake_response.headers.replace_header(
            "Content-Type",
            "application/ld+json; charset=utf-8",
        )
        with (
            patch("helpers.build_opener") as build_safe_opener,
            patch("helpers.log_api_communication"),
        ):
            build_safe_opener.return_value.open.return_value = fake_response

            reply = get_espn_json(
                "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/teams"
            )

        self.assertEqual(reply, {"sports": []})

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

    def test_http_error_is_logged_with_its_status_and_reference(self) -> None:
        """A failed ESPN response should log its HTTP status and reference."""
        http_error = HTTPError(
            "https://site.api.espn.com/scoreboard",
            503,
            "Service Unavailable",
            {},
            BytesIO(b"Service is unavailable"),
        )
        with (
            patch("helpers.build_opener") as build_safe_opener,
            patch("helpers.log_api_communication") as log_communication,
        ):
            build_safe_opener.return_value.open.side_effect = http_error

            with self.assertRaisesRegex(FootballDataError, "503"):
                get_espn_json(
                    "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard"
                )

        logged_values = log_communication.call_args.args
        self.assertEqual(logged_values[0], "GET")
        self.assertIn("Service is unavailable", logged_values[2])
        self.assertEqual(logged_values[3], 503)
        self.assertTrue(logged_values[4])

    def test_safe_espn_image_address_returns_png_bytes(self) -> None:
        """An approved ESPN badge image should be downloaded as PNG bytes."""
        fake_response = FakeJsonResponse({})
        fake_response.reply_bytes = b"\x89PNG\r\n\x1a\ntest image"
        fake_response.headers["Content-Type"] = "image/png"
        with (
            patch("helpers.build_opener") as build_safe_opener,
            patch("helpers.log_api_communication") as log_communication,
        ):
            build_safe_opener.return_value.open.return_value = fake_response

            image_bytes = get_espn_image(
                "https://a.espncdn.com/i/teamlogos/test.png"
            )

        self.assertTrue(image_bytes.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(log_communication.call_args.args[0], "GET image")
        self.assertEqual(log_communication.call_args.args[3], 200)

    def test_unapproved_image_site_is_rejected_without_a_connection(self) -> None:
        """Badge links from any website other than ESPN must be rejected."""
        with (
            patch("helpers.build_opener") as build_safe_opener,
            patch("helpers.log_api_communication"),
        ):
            with self.assertRaisesRegex(FootballDataError, "image website"):
                get_espn_image("https://images.example/team.png")

        build_safe_opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
