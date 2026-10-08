"""Ask ESPN for real leagues, teams, and football match information."""

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode

from config import ALL_TEAMS_LABEL, ESPN_API_ROOT, FOOTBALL_LEAGUES
from helpers import FootballDataError, clean_words, get_espn_json


@dataclass(frozen=True)
class FootballTeam:
    """Keep a team's readable name and its ESPN team number."""

    name: str
    team_id: str


@dataclass(frozen=True)
class FootballMatch:
    """Keep the real teams, score, time, place, and status of one match."""

    match_time: str
    home_team: str
    home_score: str
    away_team: str
    away_score: str
    match_status: str
    venue: str


def get_football_teams(league_name: str) -> list[FootballTeam]:
    """Get the current team list for one of the supported ESPN leagues."""
    league_code = get_league_code(league_name)
    request_address = (
        f"{ESPN_API_ROOT}/{league_code}/teams?"
        f"{urlencode({'limit': 1000})}"
    )
    reply = get_espn_json(request_address)
    sports = reply.get("sports")
    if not isinstance(sports, list):
        raise FootballDataError(
            f"ESPN did not return a team list for {league_name}."
        )

    teams: list[FootballTeam] = []
    for sport in sports:
        if not isinstance(sport, dict):
            continue
        leagues = sport.get("leagues")
        if not isinstance(leagues, list):
            continue
        for league in leagues:
            if not isinstance(league, dict):
                continue
            team_entries = league.get("teams")
            if not isinstance(team_entries, list):
                continue
            for team_entry in team_entries:
                team = get_team_from_entry(team_entry)
                if team is not None:
                    teams.append(team)

    if not teams:
        raise FootballDataError(
            f"ESPN did not list any teams for {league_name}. Please try again later."
        )
    return sorted(teams, key=lambda team: team.name.casefold())


def get_matches(
    league_name: str,
    team_id: str | None = None,
) -> tuple[list[FootballMatch], str]:
    """Get current league fixtures or a selected team's season schedule."""
    league_code = get_league_code(league_name)
    if team_id is None:
        request_address = (
            f"{ESPN_API_ROOT}/{league_code}/scoreboard?"
            f"{urlencode({'limit': 100})}"
        )
    else:
        if not team_id.isdigit():
            raise FootballDataError("The selected team number is not valid.")
        request_address = (
            f"{ESPN_API_ROOT}/{league_code}/teams/{team_id}/schedule"
        )

    reply = get_espn_json(request_address)
    events = reply.get("events")
    if not isinstance(events, list):
        raise FootballDataError(
            "ESPN did not return the expected match list. Please try again later."
        )

    matches = [
        match
        for event in events
        if (match := make_match_from_event(event)) is not None
    ]
    matches.sort(key=lambda match: match.match_time)
    checked_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    return matches, checked_at


def get_league_code(league_name: str) -> str:
    """Find the ESPN code only for a league shown in the league list."""
    league_code = FOOTBALL_LEAGUES.get(league_name)
    if league_code is None:
        raise FootballDataError(
            "Choose a football league from the list before asking ESPN."
        )
    return league_code


def get_team_from_entry(team_entry: object) -> FootballTeam | None:
    """Read one team from ESPN's nested team list when its details are valid."""
    if not isinstance(team_entry, dict):
        return None
    team_data = team_entry.get("team")
    if not isinstance(team_data, dict):
        return None

    team_name = clean_words(team_data.get("displayName"), "")
    team_id = clean_words(team_data.get("id"), "")
    if not team_name or not team_id.isdigit():
        return None
    return FootballTeam(team_name, team_id)


def make_match_from_event(event: object) -> FootballMatch | None:
    """Turn one ESPN match into easy-to-read match details."""
    if not isinstance(event, dict):
        return None
    competitions = event.get("competitions")
    if not isinstance(competitions, list) or not competitions:
        return None
    competition = competitions[0]
    if not isinstance(competition, dict):
        return None
    competitors = competition.get("competitors")
    if not isinstance(competitors, list):
        return None

    home_team = None
    away_team = None
    for competitor in competitors:
        if not isinstance(competitor, dict):
            continue
        team_data = competitor.get("team")
        if not isinstance(team_data, dict):
            continue
        readable_team = {
            "name": clean_words(team_data.get("displayName")),
            "score": get_display_score(competitor.get("score")),
        }
        if competitor.get("homeAway") == "home":
            home_team = readable_team
        elif competitor.get("homeAway") == "away":
            away_team = readable_team

    if home_team is None or away_team is None:
        return None

    venue_data = competition.get("venue")
    venue_name = (
        clean_words(venue_data.get("fullName"))
        if isinstance(venue_data, dict)
        else "Venue not available"
    )
    return FootballMatch(
        match_time=make_readable_match_time(competition.get("date")),
        home_team=home_team["name"],
        home_score=home_team["score"],
        away_team=away_team["name"],
        away_score=away_team["score"],
        match_status=get_match_status(competition.get("status")),
        venue=venue_name,
    )


def get_display_score(score_value: object) -> str:
    """Read the score ESPN has supplied, without inventing a score."""
    if isinstance(score_value, dict):
        return clean_words(
            score_value.get("displayValue"),
            "Not played",
        )
    return clean_words(score_value, "Not played")


def get_match_status(status_value: object) -> str:
    """Read ESPN's match status in everyday words."""
    if not isinstance(status_value, dict):
        return "Status not available"
    status_type = status_value.get("type")
    if isinstance(status_type, dict):
        return clean_words(
            status_type.get("detail"),
            clean_words(status_type.get("description"), "Status not available"),
        )
    return "Status not available"


def make_readable_match_time(date_value: object) -> str:
    """Show ESPN's match date and time in the computer's local time zone."""
    if not isinstance(date_value, str):
        return "Time not available"
    try:
        match_date = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
    except ValueError:
        return clean_words(date_value, "Time not available")
    return match_date.astimezone().strftime("%a %d %b %Y, %H:%M")


def format_match_list(
    league_name: str,
    selected_team: str,
    matches: list[FootballMatch],
    checked_at: str,
) -> str:
    """Make a clear report from ESPN's matches without adding made-up facts."""
    selected_group = (
        league_name
        if selected_team == ALL_TEAMS_LABEL
        else f"{league_name} - {selected_team}"
    )
    report_lines = [
        f"Football results and fixtures: {selected_group}",
        f"Information checked: {checked_at}",
        "Scores and match details below are supplied by ESPN.",
        "",
    ]
    if not matches:
        report_lines.append(
            "ESPN has no matches to show for this selection right now."
        )
        return "\n".join(report_lines)

    for match in matches:
        report_lines.extend(
            [
                f"{match.match_time} | {match.match_status}",
                f"{match.home_team} {match.home_score} - "
                f"{match.away_score} {match.away_team}",
                f"Venue: {match.venue}",
                "",
            ]
        )
    return "\n".join(report_lines).rstrip()
