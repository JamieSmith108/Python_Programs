"""Check that ESPN's football information is read and shown correctly."""

import unittest
from unittest.mock import Mock, patch

from config import FOOTBALL_LEAGUES, LEAGUE_SELECTION_PROMPT
from football_api import (
    FootballMatch,
    FootballStanding,
    find_standing_groups,
    format_league_table,
    format_match_list,
    get_football_teams,
    get_league_badge_bytes,
    get_league_code,
    get_league_table,
    get_matches,
    make_standing_from_entry,
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

    def test_league_table_is_loaded_with_the_teams(self) -> None:
        """The league table should be requested as part of league selection."""
        window = object.__new__(FootballMonitorWindow)
        teams = [Mock()]
        badge = b"league badge"
        table_rows = [
            FootballStanding("", "1", "Arsenal", "1", "1", "0", "0",
                             "2", "0", "2", "3")
        ]

        with (
            patch("gui.get_football_teams", return_value=teams),
            patch("gui.get_league_badge_bytes", return_value=badge),
            patch("gui.get_league_table", return_value=table_rows) as get_table,
        ):
            result = window.load_league_selection_data("English Premier League")

        self.assertEqual(result[0:2], (teams, badge))
        self.assertIn("Arsenal", result[2])
        get_table.assert_called_once_with("English Premier League")

    def test_table_error_does_not_prevent_loading_teams(self) -> None:
        """A missing ESPN table should not stop the team menu from working."""
        window = object.__new__(FootballMonitorWindow)
        teams = [Mock()]

        with (
            patch("gui.get_football_teams", return_value=teams),
            patch("gui.get_league_badge_bytes", return_value=None),
            patch(
                "gui.get_league_table",
                side_effect=FootballDataError("ESPN table is unavailable."),
            ),
            patch("gui.log_application_error") as log_error,
        ):
            loaded_teams, _, table_report = window.load_league_selection_data(
                "English Premier League"
            )

        self.assertEqual(loaded_teams, teams)
        self.assertIn("table information could not be loaded", table_report)
        log_error.assert_called_once()

    def test_loaded_league_table_is_shown_in_its_tab(self) -> None:
        """The table report should be sent to the Table tab after loading."""
        window = object.__new__(FootballMonitorWindow)
        window.selected_league = Mock()
        window.selected_league.get.return_value = "English Premier League"
        window.team_ids_by_name = {}
        window.teams_by_name = {}
        window.team_menu = Mock()
        window.show_badge = Mock()
        window.show_table = Mock()
        window.status_message = Mock()

        with patch("gui.log_application_activity"):
            window.finish_loading_teams(
                "English Premier League",
                [],
                None,
                "Current table report",
            )

        window.show_table.assert_called_once_with("Current table report")

    def test_turning_off_the_selected_league_clears_its_team(self) -> None:
        """Remove old team data when its league is no longer in the menu."""
        window = object.__new__(FootballMonitorWindow)
        window.selected_leagues = ["English Premier League"]
        window.selected_league = Mock()
        window.selected_league.get.return_value = "English Premier League"
        window.selected_team = Mock()
        window.request_number = 2
        window.team_ids_by_name = {"Arsenal": "359"}
        window.teams_by_name = {"Arsenal": Mock()}
        window.league_menu = Mock()
        window.team_menu = Mock()
        window.status_message = Mock()
        window.show_badge = Mock()
        window.show_results = Mock()
        window.show_table = Mock()

        window.apply_selected_leagues(["Spanish LaLiga"])

        self.assertEqual(window.selected_leagues, ["Spanish LaLiga"])
        window.selected_league.set.assert_called_once_with(LEAGUE_SELECTION_PROMPT)
        self.assertEqual(window.request_number, 3)
        self.assertEqual(window.team_ids_by_name, {})
        self.assertEqual(window.teams_by_name, {})
        window.team_menu.configure.assert_called_once_with(
            values=["All teams in this league"],
            state="disabled",
        )

    def test_league_stays_selected_when_it_remains_enabled(self) -> None:
        """Keep current results if the selected league stays checked."""
        window = object.__new__(FootballMonitorWindow)
        window.selected_leagues = ["English Premier League"]
        window.selected_league = Mock()
        window.selected_league.get.return_value = "English Premier League"
        window.league_menu = Mock()
        window.request_number = 2
        window.show_badge = Mock()

        window.apply_selected_leagues(
            ["English Premier League", "Spanish LaLiga"]
        )

        self.assertEqual(window.request_number, 2)
        window.selected_league.set.assert_not_called()

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

    def test_team_choices_use_scoreboard_when_espn_team_list_is_empty(self) -> None:
        """Use real match participants when ESPN has no Irish team list."""
        teams_reply = {
            "sports": [
                {"leagues": [{"teams": []}]}
            ]
        }
        scoreboard_reply = {
            "events": [
                {
                    "competitions": [
                        {
                            "competitors": [
                                {
                                    "team": {
                                        "displayName": "Derry City",
                                        "id": "600",
                                    }
                                },
                                {
                                    "team": {
                                        "displayName": "Bohemians",
                                        "id": "601",
                                    }
                                },
                            ]
                        }
                    ]
                },
                {
                    "competitions": [
                        {
                            "competitors": [
                                {
                                    "team": {
                                        "displayName": "Derry City",
                                        "id": "600",
                                    }
                                },
                                {
                                    "team": {
                                        "displayName": "Shamrock Rovers",
                                        "id": "602",
                                    }
                                },
                            ]
                        }
                    ]
                },
            ]
        }

        with patch(
            "football_api.get_espn_json",
            side_effect=[teams_reply, scoreboard_reply],
        ) as get_reply:
            teams = get_football_teams("Irish Premier Division")

        self.assertEqual(
            [(team.name, team.team_id) for team in teams],
            [
                ("Bohemians", "601"),
                ("Derry City", "600"),
                ("Shamrock Rovers", "602"),
            ],
        )
        self.assertIn("/irl.1/scoreboard?", get_reply.call_args.args[0])

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

    def test_league_table_is_read_from_espn_standings(self) -> None:
        """Read team names and season totals from ESPN's table response."""
        standings_reply = {
            "children": [
                {
                    "name": "Premier League",
                    "standings": {
                        "entries": [
                            {
                                "team": {"displayName": "Arsenal"},
                                "stats": [
                                    {"name": "gamesPlayed", "value": 8},
                                    {"name": "wins", "value": 6},
                                    {"name": "ties", "value": 1},
                                    {"name": "losses", "value": 1},
                                    {"name": "pointsFor", "value": 16},
                                    {"name": "pointsAgainst", "value": 5},
                                    {"name": "points", "value": 19},
                                ],
                            }
                        ]
                    },
                }
            ]
        }

        with patch(
            "football_api.get_espn_json",
            return_value=standings_reply,
        ) as get_reply:
            table_rows = get_league_table("English Premier League")

        self.assertEqual(
            table_rows,
            [
                FootballStanding(
                    "Premier League",
                    "1",
                    "Arsenal",
                    "8",
                    "6",
                    "1",
                    "1",
                    "16",
                    "5",
                    "11",
                    "19",
                )
            ],
        )
        self.assertEqual(
            get_reply.call_args.args[0],
            "https://site.api.espn.com/apis/v2/sports/soccer/eng.1/standings",
        )

    def test_empty_espn_table_does_not_make_up_standings(self) -> None:
        """An empty ESPN response should return no imaginary league rows."""
        with patch("football_api.get_espn_json", return_value={}):
            self.assertEqual(get_league_table("English Premier League"), [])

        report = format_league_table("English Premier League", [])

        self.assertIn(
            "ESPN has not supplied current table information",
            report,
        )

    def test_table_finds_direct_entries_without_duplicate_rows(self) -> None:
        """An entries list nested inside standings should only be read once."""
        table_reply = {
            "standings": {
                "entries": [
                    {"team": {"displayName": "Arsenal"}, "stats": []}
                ]
            }
        }

        self.assertEqual(
            len(find_standing_groups(table_reply)),
            1,
        )

    def test_table_skips_entries_without_a_team_name(self) -> None:
        """Do not display broken ESPN table rows as real football teams."""
        self.assertIsNone(
            make_standing_from_entry({"team": {}}, "", 1)
        )

    def test_table_report_shows_positions_points_and_goal_difference(self) -> None:
        """The table display should include each team's main league totals."""
        standing = FootballStanding(
            "",
            "1",
            "Arsenal",
            "8",
            "6",
            "1",
            "1",
            "16",
            "5",
            "11",
            "19",
        )

        report = format_league_table("English Premier League", [standing])

        self.assertIn("Pos", report)
        self.assertIn("Arsenal", report)
        self.assertIn("19", report)
        self.assertIn("11", report)

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
