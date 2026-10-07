"""Check that TVMaze show information is read correctly."""

import unittest

from tvmaze_api import make_show_details


class ShowDetailsTests(unittest.TestCase):
    """Check the conversion from a TVMaze answer to show details."""

    def test_make_show_details_reads_available_values(self) -> None:
        """Useful show information should be ready to display."""
        show_details = make_show_details(
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

        self.assertEqual(show_details.name, "Example Show")
        self.assertEqual(show_details.genres, "Drama, Mystery")
        self.assertEqual(show_details.runtime, "45")
        self.assertEqual(show_details.rating, "8.25 out of 10")
        self.assertEqual(show_details.channel, "Example TV")
        self.assertEqual(show_details.schedule, "Monday at 20:00")
        self.assertEqual(show_details.summary, "A good show.")

    def test_make_show_details_uses_web_channel_when_no_network_exists(self) -> None:
        """Online shows should display their web channel."""
        show_details = make_show_details(
            {
                "name": "Online Show",
                "webChannel": {"name": "Example Stream"},
            }
        )

        self.assertEqual(show_details.channel, "Example Stream")
        self.assertEqual(show_details.rating, "Not available")
        self.assertEqual(show_details.schedule, "Not available")


if __name__ == "__main__":
    unittest.main()
