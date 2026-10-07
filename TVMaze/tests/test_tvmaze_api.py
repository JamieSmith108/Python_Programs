"""Check that TVMaze show information is read correctly."""

import unittest
import json
from unittest.mock import patch

from config import AppSettings
from presentation import format_program_details
from tvmaze_api import (
    MAX_PROGRAM_NAME_CHARACTERS,
    TVMazeError,
    find_program_choices,
    find_program_details,
    find_picture_url,
    format_program_field,
    make_program_details,
    make_english_time,
    make_program_years,
)


class ProgramDetailsTests(unittest.TestCase):
    """Check the conversion from a TVMaze answer to show details."""

    def test_program_details_read_available_values(self) -> None:
        """Useful show information should be ready to display."""
        program = make_program_details(
            {
                "name": "Example Show",
                "type": "Scripted",
                "language": "English",
                "genres": ["Drama", "Mystery"],
                "status": "Running",
                "premiered": "2020-01-01",
                "ended": None,
                "runtime": 45,
                "rating": {"average": 8.25},
                "network": {"name": "Example TV"},
                "schedule": {"days": ["Monday"], "time": "20:00"},
                "officialSite": "https://example.com",
                "summary": "<p>A <b>good</b> show.</p>",
            }
        )

        self.assertEqual(program.fields["name"], "Example Show")
        self.assertEqual(program.fields["genres"], "Drama, Mystery")
        self.assertEqual(program.fields["runtime"], "45 minutes")
        self.assertEqual(program.fields["premiered"], "January 1, 2020")
        self.assertEqual(program.fields["rating"], "8.25 out of 10")
        self.assertEqual(program.fields["network"], "Example TV")
        self.assertEqual(program.fields["schedule"], "Monday at 8:00 PM")
        self.assertEqual(program.fields["summary"], "A good show.")

    def test_program_details_use_web_channel_when_no_network_exists(self) -> None:
        """Online shows should display their web channel."""
        program = make_program_details(
            {
                "name": "Online Show",
                "webChannel": {"name": "Example Stream"},
            }
        )

        self.assertEqual(
            program.fields["webChannel"],
            "Example Stream",
        )
        self.assertEqual(program.fields["rating"], "Not available")
        self.assertEqual(program.fields["schedule"], "Not available")

    def test_results_show_only_the_selected_fields(self) -> None:
        """The results should include checked fields and leave out unchecked ones."""
        program = make_program_details(
            {
                "id": 123,
                "name": "Example Show",
            }
        )

        result_text = format_program_details(program, ("id",))

        self.assertEqual(result_text, "Show ID: 123")

    def test_nested_values_use_readable_english_labels(self) -> None:
        """Nested network details should not contain JSON punctuation."""
        program = make_program_details(
            {
                "network": {
                    "name": "BBC One",
                    "country": {
                        "name": "United Kingdom",
                        "code": "GB",
                    },
                }
            }
        )

        network_text = program.fields["network"]

        self.assertIn("BBC One", network_text)
        self.assertIn("Country: United Kingdom", network_text)
        self.assertIn("Code: GB", network_text)
        self.assertNotIn("{", network_text)
        self.assertNotIn('"', network_text)

    def test_medium_image_url_uses_tvmaze_small_poster(self) -> None:
        """The program should choose the smaller poster when one is available."""
        picture_url = find_picture_url(
            {
                "medium": (
                    "https://static.tvmaze.com/uploads/images/"
                    "medium_portrait/0/1.jpg"
                ),
                "original": (
                    "https://static.tvmaze.com/uploads/images/"
                    "original_untouched/0/1.jpg"
                ),
            }
        )

        self.assertEqual(
            picture_url,
            "https://static.tvmaze.com/uploads/images/medium_portrait/0/1.jpg",
        )

    def test_picture_address_from_an_untrusted_website_is_rejected(self) -> None:
        """A show picture must not come from a website other than TVMaze's."""
        unsafe_picture_addresses = (
            "https://images.example/poster.jpg",
            "https://static.tvmaze.com.evil.example/uploads/images/poster.jpg",
            "http://static.tvmaze.com/uploads/images/poster.jpg",
            "https://static.tvmaze.com/other-place/poster.jpg",
            "https://static.tvmaze.com/uploads/images/poster.svg",
            "https://static.tvmaze.com/uploads/images/poster.jpg?next=evil",
        )

        for unsafe_address in unsafe_picture_addresses:
            with self.subTest(address=unsafe_address):
                self.assertIsNone(
                    find_picture_url(
                        {"medium": unsafe_address, "original": unsafe_address}
                    )
                )

    def test_blank_program_name_is_rejected_before_a_web_request(self) -> None:
        """An empty program name must never be sent to a website."""
        with patch("tvmaze_api.open_trusted_tvmaze_request") as open_web_request:
            with self.assertRaisesRegex(TVMazeError, "Enter a TV program name"):
                find_program_details("   ")

        open_web_request.assert_not_called()

    def test_very_long_program_name_is_rejected_before_a_web_request(self) -> None:
        """A name longer than the safe limit must not be sent to the API."""
        too_long_name = "A" * (MAX_PROGRAM_NAME_CHARACTERS + 1)

        with patch("tvmaze_api.open_trusted_tvmaze_request") as open_web_request:
            with self.assertRaisesRegex(TVMazeError, "characters or fewer"):
                find_program_details(too_long_name)

        open_web_request.assert_not_called()

    def test_unapproved_settings_are_rejected_before_a_web_request(self) -> None:
        """A hand-built setting cannot bypass the official website check."""
        unsafe_settings = AppSettings(
            tvmaze_api_url="https://evil.example/collect",
        )

        with patch("tvmaze_api.open_trusted_tvmaze_request") as open_web_request:
            with self.assertRaisesRegex(TVMazeError, "official secure TVMaze"):
                find_program_details("Doctor Who", unsafe_settings)

        open_web_request.assert_not_called()

    def test_untrusted_picture_address_is_never_requested(self) -> None:
        """A fake picture website in an API reply must never be contacted."""
        api_reply = json.dumps(
            {
                "name": "Example Show",
                "image": {
                    "medium": "https://evil.example/collect.jpg",
                    "original": "https://evil.example/collect.jpg",
                },
            }
        ).encode("utf-8")
        settings = AppSettings(selected_show_fields=("image",))

        with patch("tvmaze_api.request_tvmaze", return_value=api_reply) as request:
            program = find_program_details("Example Show", settings)

        request.assert_called_once()
        self.assertIn("not from the TVMaze picture website", program.fields["image"])

    def test_picture_download_problem_is_logged_and_other_details_remain(self) -> None:
        """A broken picture should be logged without losing show details."""
        api_reply = json.dumps(
            {
                "name": "Example Show",
                "image": {
                    "medium": (
                        "https://static.tvmaze.com/uploads/images/"
                        "medium_portrait/1/1.jpg"
                    )
                },
            }
        ).encode("utf-8")
        with (
            patch(
                "tvmaze_api.request_tvmaze",
                side_effect=[api_reply, OSError("Picture server unavailable")],
            ),
            patch("tvmaze_api.log_application_error") as log_problem,
        ):
            program = find_program_details(
                "Example Show",
                AppSettings(selected_show_fields=("name", "image")),
            )

        self.assertEqual(program.fields["name"], "Example Show")
        self.assertEqual(
            program.fields["image"],
            "The show image could not be downloaded.",
        )
        log_problem.assert_called_once()
        self.assertEqual(
            log_problem.call_args.args[0],
            "downloading a show picture",
        )

    def test_same_name_results_include_years_and_picture_data(self) -> None:
        """Duplicate exact titles should become complete choices for the window."""
        search_reply = json.dumps(
            [
                {
                    "show": {
                        "name": "Shared Show",
                        "premiered": "1990-01-01",
                        "ended": "1992-12-31",
                        "image": {
                            "medium": (
                                "https://static.tvmaze.com/uploads/images/"
                                "medium_portrait/1/1.jpg"
                            )
                        },
                    }
                },
                {
                    "show": {
                        "name": " shared show ",
                        "premiered": "2010-01-01",
                        "ended": None,
                        "image": {
                            "medium": (
                                "https://static.tvmaze.com/uploads/images/"
                                "medium_portrait/2/2.jpg"
                            )
                        },
                    }
                },
                {"show": {"name": "Similar, but different"}},
            ]
        ).encode("utf-8")
        with patch(
            "tvmaze_api.request_tvmaze",
            side_effect=[search_reply, b"first picture", b"second picture"],
        ) as request:
            choices = find_program_choices("Shared Show")

        self.assertEqual(len(choices), 2)
        self.assertEqual(choices[0].program.fields["name"], "Shared Show")
        self.assertEqual(choices[0].years_ran, "1990 to 1992")
        self.assertEqual(choices[0].program.image_data, b"first picture")
        self.assertEqual(choices[1].years_ran, "2010 to present")
        self.assertEqual(choices[1].program.image_data, b"second picture")
        self.assertEqual(request.call_count, 3)
        self.assertIn("/search/shows?q=Shared+Show", request.call_args_list[0].args[0])

    def test_one_exact_name_result_does_not_add_similar_title(self) -> None:
        """Similar titles should not appear as duplicate-name choices."""
        search_reply = json.dumps(
            [
                {"show": {"name": "A Shared Show"}},
                {"show": {"name": "Shared Show", "premiered": "2000-01-01"}},
            ]
        ).encode("utf-8")
        with patch("tvmaze_api.request_tvmaze", return_value=search_reply):
            choices = find_program_choices("Shared Show")

        self.assertEqual(len(choices), 1)
        self.assertEqual(choices[0].program.fields["name"], "Shared Show")
        self.assertEqual(choices[0].years_ran, "2000 to present")

    def test_years_are_clear_when_tvmaze_dates_are_missing(self) -> None:
        """Missing or invalid dates should have a clear, honest label."""
        self.assertEqual(
            make_program_years(None, "2015-01-01"),
            "Start year unknown to 2015",
        )
        self.assertEqual(make_program_years("not a date", None), "Years not available")

    def test_schedule_uses_a_familiar_clock_time(self) -> None:
        """A schedule time should use the common twelve-hour clock."""
        schedule_text = format_program_field(
            "schedule",
            {"days": ["Sunday"], "time": "20:00"},
        )

        self.assertEqual(schedule_text, "Sunday at 8:00 PM")

    def test_time_without_minutes_stays_readable(self) -> None:
        """A time that cannot be read as a clock should stay unchanged."""
        self.assertEqual(make_english_time("after lunch"), "after lunch")


if __name__ == "__main__":
    unittest.main()
