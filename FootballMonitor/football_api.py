"""Ask ESPN for real leagues, teams, and football match information."""

from dataclasses import dataclass
from datetime import datetime

from config import (
    ALL_TEAMS_LABEL,
    ESPN_API_ROOT,
    ESPN_STANDINGS_API_ROOT,
    FOOTBALL_LEAGUES,
)
from helpers import (
    FootballDataError,
    clean_words,
    get_espn_json,
    get_optional_espn_image,
    make_espn_api_address,
)


@dataclass(frozen=True)
class FootballTeam:
    """Keep a team's readable name and its ESPN team number."""

    name: str
    team_id: str
    badge_url: str = ""


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


@dataclass(frozen=True)
class FootballStanding:
    """Keep one team's place and season totals from ESPN's league table."""

    group_name: str
    position: str
    team_name: str
    matches_played: str
    wins: str
    draws: str
    losses: str
    goals_for: str
    goals_against: str
    goal_difference: str
    points: str


def get_football_teams(league_name: str) -> list[FootballTeam]:
    """Get the current team list for one of the supported ESPN leagues."""
    league_code = get_league_code(league_name)
    request_address = make_espn_api_address(
        ESPN_API_ROOT,
        league_code,
        "teams",
        {"limit": 1000},
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
        scoreboard_address = make_espn_api_address(
            ESPN_API_ROOT,
            league_code,
            "scoreboard",
            {"limit": 100},
        )
        scoreboard_reply = get_espn_json(scoreboard_address)
        teams = get_teams_from_scoreboard(scoreboard_reply)

    if not teams:
        raise FootballDataError(
            f"ESPN did not list any teams for {league_name}. Please try again later."
        )
    return sorted(teams, key=lambda team: team.name.casefold())


def get_teams_from_scoreboard(reply: dict[str, object]) -> list[FootballTeam]:
    """Find unique team choices in ESPN matches when its team list is empty."""
    events = reply.get("events")
    if not isinstance(events, list):
        return []

    teams_by_id: dict[str, FootballTeam] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        competitions = event.get("competitions")
        if not isinstance(competitions, list):
            continue
        for competition in competitions:
            if not isinstance(competition, dict):
                continue
            competitors = competition.get("competitors")
            if not isinstance(competitors, list):
                continue
            for competitor in competitors:
                if not isinstance(competitor, dict):
                    continue
                team = get_team_from_entry({"team": competitor.get("team")})
                if team is not None:
                    teams_by_id[team.team_id] = team
    return list(teams_by_id.values())


def get_league_badge_bytes(league_name: str) -> bytes | None:
    """Download the selected league badge that ESPN lists on its scoreboard."""
    league_code = get_league_code(league_name)
    request_address = make_espn_api_address(
        ESPN_API_ROOT,
        league_code,
        "scoreboard",
        {"limit": 1},
    )
    reply = get_espn_json(request_address)
    leagues = reply.get("leagues")
    if not isinstance(leagues, list) or not leagues:
        return None
    league_data = leagues[0]
    if not isinstance(league_data, dict):
        return None
    logo_url = get_default_logo_url(league_data.get("logos"))
    if not logo_url:
        return None
    return get_optional_espn_image(
        logo_url,
        "loading the selected league badge",
        "Check the internet connection. The league and teams can still be "
        "used without a badge.",
    )


def get_league_table(league_name: str) -> list[FootballStanding]:
    """Get the current league table from ESPN when that league provides one."""
    league_code = get_league_code(league_name)
    request_address = make_espn_api_address(
        ESPN_STANDINGS_API_ROOT,
        league_code,
        "standings",
    )
    reply = get_espn_json(request_address)
    grouped_entries = find_standing_groups(reply)
    table_rows: list[FootballStanding] = []
    for group_name, entries in grouped_entries:
        for row_number, entry in enumerate(entries, start=1):
            standing = make_standing_from_entry(
                entry,
                group_name,
                row_number,
            )
            if standing is not None:
                table_rows.append(standing)
    return table_rows


def find_standing_groups(
    reply: dict[str, object],
) -> list[tuple[str, list[object]]]:
    """Find ESPN table rows in a league table or its separate groups."""
    standing_groups: list[tuple[str, list[object]]] = []

    def visit_table_part(table_part: object, group_name: str = "") -> None:
        """Look inside one ESPN table section for rows and smaller sections."""
        if not isinstance(table_part, dict):
            return
        table_name = clean_words(table_part.get("name"), group_name)
        standings = table_part.get("standings")
        if isinstance(standings, dict):
            visit_table_part(standings, table_name)
        direct_entries = table_part.get("entries")
        if isinstance(direct_entries, list) and not isinstance(standings, dict):
            standing_groups.append((table_name, direct_entries))
        children = table_part.get("children")
        if isinstance(children, list):
            for child in children:
                visit_table_part(child, table_name)

    visit_table_part(reply)
    return standing_groups


def make_standing_from_entry(
    entry: object,
    group_name: str,
    row_number: int,
) -> FootballStanding | None:
    """Turn one ESPN table row into simple football league statistics."""
    if not isinstance(entry, dict):
        return None
    team_data = entry.get("team")
    if not isinstance(team_data, dict):
        return None
    team_name = clean_words(
        team_data.get("displayName"),
        clean_words(team_data.get("name"), ""),
    )
    if not team_name:
        return None

    statistics = make_statistic_lookup(entry.get("stats"))
    goals_for = find_statistic(statistics, ("pointsFor", "goalsFor"))
    goals_against = find_statistic(
        statistics,
        ("pointsAgainst", "goalsAgainst"),
    )
    goal_difference = find_statistic(
        statistics,
        ("pointDifferential", "goalDifference", "goalDiff"),
    )
    if goal_difference == "—":
        goal_difference = calculate_goal_difference(goals_for, goals_against)

    position = find_statistic(
        statistics,
        ("rank", "position", "playoffSeed", "seed"),
    )
    if position == "—":
        position = clean_words(entry.get("rank"), str(row_number))
    group_name = (
        ""
        if group_name.casefold() == team_name.casefold()
        else group_name
    )
    return FootballStanding(
        group_name=group_name,
        position=position,
        team_name=team_name,
        matches_played=find_statistic(
            statistics,
            ("gamesPlayed", "matchesPlayed", "played"),
        ),
        wins=find_statistic(statistics, ("wins", "won")),
        draws=find_statistic(statistics, ("ties", "draws", "drawn")),
        losses=find_statistic(statistics, ("losses", "lost")),
        goals_for=goals_for,
        goals_against=goals_against,
        goal_difference=goal_difference,
        points=find_statistic(statistics, ("points", "leaguePoints")),
    )


def make_statistic_lookup(statistics: object) -> dict[str, str]:
    """Make ESPN's named statistics easy to find without guessing values."""
    if not isinstance(statistics, list):
        return {}
    statistic_values: dict[str, str] = {}
    for statistic in statistics:
        if not isinstance(statistic, dict):
            continue
        statistic_value = clean_words(
            statistic.get("displayValue"),
            clean_words(statistic.get("value"), "—"),
        )
        for statistic_name in (
            statistic.get("name"),
            statistic.get("abbreviation"),
        ):
            if isinstance(statistic_name, str):
                statistic_values[statistic_name.casefold()] = statistic_value
    return statistic_values


def find_statistic(
    statistics: dict[str, str],
    possible_names: tuple[str, ...],
) -> str:
    """Read the first available ESPN statistic from its known names."""
    for possible_name in possible_names:
        statistic_value = statistics.get(possible_name.casefold())
        if statistic_value is not None:
            return statistic_value
    return "—"


def calculate_goal_difference(goals_for: str, goals_against: str) -> str:
    """Calculate goal difference only when ESPN supplies both goal totals."""
    try:
        return str(int(float(goals_for)) - int(float(goals_against)))
    except ValueError:
        return "—"


def format_league_table(
    league_name: str,
    table_rows: list[FootballStanding],
) -> str:
    """Show ESPN's current table in a clear, easy-to-read text layout."""
    if not table_rows:
        return (
            f"Current table: {league_name}\n\n"
            "ESPN has not supplied current table information for this league."
        )

    table_lines = [
        f"Current table: {league_name}",
        "All table information below is supplied by ESPN.",
        "",
    ]
    active_group = ""
    table_lines.append(
        "Pos  Team                           P    W    D    L    GF   GA   GD   Pts"
    )
    table_lines.append(
        "---  -----------------------------  ---  ---  ---  ---  ---  ---  ---  ---"
    )
    for standing in table_rows:
        if standing.group_name and standing.group_name != active_group:
            active_group = standing.group_name
            table_lines.extend(["", active_group])
        table_lines.append(
            f"{standing.position:>3}  "
            f"{standing.team_name[:29]:<29}  "
            f"{standing.matches_played:>3}  "
            f"{standing.wins:>3}  "
            f"{standing.draws:>3}  "
            f"{standing.losses:>3}  "
            f"{standing.goals_for:>3}  "
            f"{standing.goals_against:>3}  "
            f"{standing.goal_difference:>3}  "
            f"{standing.points:>3}"
        )
    return "\n".join(table_lines)


def get_matches(
    league_name: str,
    team_id: str | None = None,
) -> tuple[list[FootballMatch], str]:
    """Get current league fixtures or a selected team's season schedule."""
    league_code = get_league_code(league_name)
    if team_id is None:
        request_address = make_espn_api_address(
            ESPN_API_ROOT,
            league_code,
            "scoreboard",
            {"limit": 100},
        )
    else:
        if not team_id.isdigit():
            raise FootballDataError("The selected team number is not valid.")
        request_address = make_espn_api_address(
            ESPN_API_ROOT,
            league_code,
            f"teams/{team_id}/schedule",
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
    team_badge_url = get_default_logo_url(team_data.get("logos"))
    return FootballTeam(team_name, team_id, team_badge_url)


def get_default_logo_url(logo_entries: object) -> str:
    """Choose ESPN's normal light-background image address from logo choices."""
    if not isinstance(logo_entries, list):
        return ""

    first_logo_url = ""
    for logo_entry in logo_entries:
        if not isinstance(logo_entry, dict):
            continue
        logo_url = clean_words(logo_entry.get("href"), "")
        if not logo_url:
            continue
        if not first_logo_url:
            first_logo_url = logo_url
        logo_relationships = logo_entry.get("rel")
        if (
            isinstance(logo_relationships, list)
            and "default" in logo_relationships
        ):
            return logo_url
    return first_logo_url


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
