"""Keep the football competitions and safe ESPN request settings together."""

ESPN_API_ROOT = "https://site.api.espn.com/apis/site/v2/sports/soccer"
ESPN_API_HOST = "site.api.espn.com"
REQUEST_TIMEOUT_SECONDS = 15
MAX_REPLY_SIZE_BYTES = 5_000_000
ALL_TEAMS_LABEL = "All teams in this league"

# The key is what people see in the league list. The value is ESPN's league code.
FOOTBALL_LEAGUES = {
    "English Premier League": "eng.1",
    "English Championship": "eng.2",
    "Spanish LaLiga": "esp.1",
    "German Bundesliga": "ger.1",
    "Italian Serie A": "ita.1",
    "French Ligue 1": "fra.1",
    "Major League Soccer (MLS)": "usa.1",
    "UEFA Champions League": "uefa.champions",
    "UEFA Europa League": "uefa.europa",
    "Liga MX": "mex.1",
    "Brazilian Serie A": "bra.1",
    "Scottish Premiership": "sco.1",
}
