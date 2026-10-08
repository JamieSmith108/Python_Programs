"""Check that ESPN's football information is read and shown correctly."""

import unittest
from unittest.mock import Mock, patch

from config import FOOTBALL_LEAGUES, LEAGUE_SELECTION_PROMPT
from football_api import (
    FootballMatch,
    format_match_list,
    get_football_teams,
    get_league_badge_bytes,
    get_league_code,
    get_matches,
    make_match_from_event,
)
from helpers import FootballDataError
from gui import FootballMonitorWindow


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

    def test_prompt_does_not_start_a_team_request(self) -> None:
        """The app must wait for a real league choice before requesting teams."""
        window = object.__new__(FootballMonitorWindow)
        window.selected_league = Mock()
        window.selected_league.get.return_value = LEAGUE_SELECTION_PROMPT
        window.team_ids_by_name = {"Old team": "1"}
        window.team_menu = Mock()
        window.league_badge_label = Mock()
        window.team_badge_label = Mock()
        window.status_message = Mock()
        window.start_background_task = Mock()

        window.load_teams_for_selected_league()

        window.start_background_task.assert_not_called()
        window.team_menu.configure.assert_called_once_with(
            values=["All teams in this league"],
            state="disabled",
        )
        self.assertEqual(window.team_ids_by_name, {})

    def test_choosing_a_team_starts_loading_its_matches(self) -> None:
        """Selecting a team should request matches without a refresh button."""
        window = object.__new__(FootballMonitorWindow)
        window.selected_league = Mock()
        window.selected_league.get.return_value = "English Premier League"
        window.selected_team = Mock()
        window.selected_team.get.return_value = "Arsenal"
        window.team_ids_by_name = {"Arsenal": "359"}
        window.teams_by_name = {
            "Arsenal": Mock(name="Arsenal", team_id="359", badge_url="")
        }
        window.show_badge = Mock()
        window.status_message = Mock()
        window.start_background_task = Mock()

        window.show_selected_matches()

        window.start_background_task.assert_called_once()
        self.assertEqual(
            window.start_background_task.call_args.args[0],
            "loading football matches",
        )

    def test_all_teams_match_loading_does_not_request_a_club_badge(self) -> None:
        """The league-wide choice should not download or show any club badge."""
        window = object.__new__(FootballMonitorWindow)
        match_list = [Mock()]
        checked_at = "2026-10-08 14:00 BST"
        with (
            patch("gui.get_matches", return_value=(match_list, checked_at)),
            patch("gui.get_espn_image") as get_image,
        ):
            result = window.load_match_details(
                "English Premier League",
                "All teams in this league",
                None,
                None,
            )

        self.assertEqual(result, (match_list, checked_at, None))
        get_image.assert_not_called()

    def test_all_teams_results_do_not_show_a_club_badge(self) -> None:
        """The league-wide results should leave the team badge area empty."""
        window = object.__new__(FootballMonitorWindow)
        window.show_results = Mock()
        window.status_message = Mock()
        window.show_badge = Mock()

        with patch("gui.log_application_activity"):
            window.finish_loading_matches(
                "English Premier League",
                "All teams in this league",
                ([], "2026-10-08 14:00 BST", b"unused badge"),
            )

        window.show_badge.assert_not_called()

    def test_selected_team_results_show_the_club_badge(self) -> None:
        """A team-specific result should display the badge returned by ESPN."""
        window = object.__new__(FootballMonitorWindow)
        window.show_results = Mock()
        window.status_message = Mock()
        window.show_badge = Mock()
        selected_badge = b"team badge"

        with patch("gui.log_application_activity"):
            window.finish_loading_matches(
                "English Premier League",
                "Arsenal",
                ([], "2026-10-08 14:00 BST", selected_badge),
            )

        window.show_badge.assert_called_once_with(selected_badge, "team")

    def test_exit_button_action_closes_the_main_window(self) -> None:
        """The Exit button action should close the program window."""
        window = object.__new__(FootballMonitorWindow)
        window.window = Mock()

        with patch("gui.log_application_activity"):
            window.exit_application()

        window.window.destroy.assert_called_once_with()

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
                                {
                                    "team": {
                                        "displayName": "Arsenal",
                                        "id": "359",
                                        "logos": [
                                            {
                                                "href": (
                                                    "https://a.espncdn.com/arsenal.png"
                                                ),
                                                "rel": ["full", "default"],
                                            }
                                        ],
                                    }
                                },
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
        self.assertEqual(
            teams[0].badge_url,
            "https://a.espncdn.com/arsenal.png",
        )

    def test_league_badge_is_downloaded_from_the_scoreboard_logo(self) -> None:
        """The league badge should use ESPN's own scoreboard logo address."""
        scoreboard_reply = {
            "leagues": [
                {
                    "logos": [
                        {
                            "href": "https://a.espncdn.com/league-default.png",
                            "rel": ["full", "default"],
                        }
                    ]
                }
            ]
        }
        badge_bytes = b"test league badge"

        with (
            patch(
                "football_api.get_espn_json",
                return_value=scoreboard_reply,
            ) as get_reply,
            patch(
                "football_api.get_espn_image",
                return_value=badge_bytes,
            ) as get_image,
        ):
            league_badge = get_league_badge_bytes("English Premier League")

        self.assertEqual(league_badge, badge_bytes)
        self.assertIn("/eng.1/scoreboard?", get_reply.call_args.args[0])
        get_image.assert_called_once_with(
            "https://a.espncdn.com/league-default.png"
        )

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
