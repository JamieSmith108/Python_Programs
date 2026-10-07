"""Check that TVMaze show information is read correctly."""

import unittest

from presentation import format_program_details
from tvmaze_api import (
    find_picture_url,
    format_program_field,
    make_program_details,
    make_english_time,
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
                "medium": "https://images.example/poster-medium.jpg",
                "original": "https://images.example/poster-original.jpg",
            }
        )

        self.assertEqual(picture_url, "https://images.example/poster-medium.jpg")

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
