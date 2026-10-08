"""Check that ESPN's football information is read and shown correctly."""

import unittest
from unittest.mock import patch

from config import FOOTBALL_LEAGUES
from football_api import (
    FootballMatch,
    format_match_list,
    get_football_teams,
    get_league_code,
    get_matches,
    make_match_from_event,
)
from helpers import FootballDataError


class FootballApiTests(unittest.TestCase):
    """Check the safe handling of league, team, and match information."""

    def test_supported_league_has_its_espn_code(self) -> None:
        """A league name from the menu should select its known ESPN code."""
        self.assertEqual(
            get_league_code("English Premier League"),
            "eng.1",
        )

    def test_only_mls_league_label_uses_the_allowed_soccer_name(self) -> None:
        """Allow the MLS name while keeping other league choices soccer-free."""
        self.assertTrue(
            all(
                "soccer" not in league_name.casefold()
                for league_name in FOOTBALL_LEAGUES
                if league_name != "Major League Soccer (MLS)"
            )
        )
        self.assertIn("Major League Soccer (MLS)", FOOTBALL_LEAGUES)

    def test_unlisted_league_is_not_sent_to_espn(self) -> None:
        """A made-up league must not be used to build a web address."""
        with self.assertRaisesRegex(FootballDataError, "Choose a football league"):
            get_league_code("A made-up league")

    def test_teams_are_read_from_the_espn_team_list(self) -> None:
        """The team menu should use names and IDs supplied by ESPN."""
        teams_reply = {
            "sports": [
                {
                    "leagues": [
                        {
                            "teams": [
                                {"team": {"displayName": "Arsenal", "id": "359"}},
                                {"team": {"displayName": "Invalid team", "id": "x"}},
                            ]
                        }
                    ]
                }
            ]
        }

        with patch("football_api.get_espn_json", return_value=teams_reply):
            teams = get_football_teams("English Premier League")

        self.assertEqual([(team.name, team.team_id) for team in teams], [("Arsenal", "359")])

    def test_all_league_match_request_uses_espn_scoreboard(self) -> None:
        """The all-teams choice should request matches for the whole league."""
        scoreboard_reply = {"events": []}

        with patch("football_api.get_espn_json", return_value=scoreboard_reply) as get_reply:
            matches, checked_at = get_matches("English Premier League")

        self.assertEqual(matches, [])
        self.assertTrue(checked_at)
        self.assertIn("/eng.1/scoreboard?", get_reply.call_args.args[0])

    def test_team_match_request_uses_the_team_schedule(self) -> None:
        """Choosing one team should show its own ESPN schedule."""
        schedule_reply = {"events": []}

        with patch("football_api.get_espn_json", return_value=schedule_reply) as get_reply:
            matches, _ = get_matches("English Premier League", "359")

        self.assertEqual(matches, [])
        self.assertIn("/eng.1/teams/359/schedule", get_reply.call_args.args[0])

    def test_invalid_team_id_is_rejected_before_a_request(self) -> None:
        """A team value that did not come from ESPN must not be requested."""
        with patch("football_api.get_espn_json") as get_reply:
            with self.assertRaisesRegex(FootballDataError, "team number is not valid"):
                get_matches("English Premier League", "../wrong-team")

        get_reply.assert_not_called()

    def test_event_is_converted_to_real_match_details(self) -> None:
        """The teams, score, kickoff, status, and venue should be read from ESPN."""
        match_event = {
            "competitions": [
                {
                    "date": "2026-10-10T11:30:00Z",
                    "status": {
                        "type": {
                            "detail": "Sat, October 10th at 7:30 AM EDT",
                        }
                    },
                    "venue": {"fullName": "Emirates Stadium"},
                    "competitors": [
                        {
                            "homeAway": "home",
                            "team": {"displayName": "Arsenal"},
                            "score": {"displayValue": "2"},
                        },
                        {
                            "homeAway": "away",
                            "team": {"displayName": "Leeds United"},
                            "score": {"displayValue": "1"},
                        },
                    ],
                }
            ]
        }

        match = make_match_from_event(match_event)

        self.assertIsNotNone(match)
        self.assertEqual(match.home_team, "Arsenal")
        self.assertEqual(match.home_score, "2")
        self.assertEqual(match.away_team, "Leeds United")
        self.assertEqual(match.away_score, "1")
        self.assertEqual(match.match_status, "Sat, October 10th at 7:30 AM EDT")
        self.assertEqual(match.venue, "Emirates Stadium")

    def test_incomplete_event_is_skipped(self) -> None:
        """A broken ESPN match item should not crash the match list."""
        self.assertIsNone(make_match_from_event({"competitions": []}))

    def test_report_says_when_information_was_checked_and_has_no_fake_games(self) -> None:
        """The report should be honest when ESPN has no matches to display."""
        report = format_match_list(
            "English Premier League",
            "All teams in this league",
            [],
            "2026-10-08 14:00 BST",
        )

        self.assertIn("Information checked: 2026-10-08 14:00 BST", report)
        self.assertIn("ESPN has no matches to show", report)

    def test_report_includes_real_match_data(self) -> None:
        """A match report should show the actual team names and scores."""
        match = FootballMatch(
            "Sat 10 Oct 2026, 12:30",
            "Arsenal",
            "2",
            "Leeds United",
            "1",
            "Full Time",
            "Emirates Stadium",
        )

        report = format_match_list(
            "English Premier League",
            "Arsenal",
            [match],
            "2026-10-08 14:00 BST",
        )

        self.assertIn("Arsenal 2 - 1 Leeds United", report)
        self.assertIn("Venue: Emirates Stadium", report)
        self.assertIn("English Premier League - Arsenal", report)


if __name__ == "__main__":
    unittest.main()
