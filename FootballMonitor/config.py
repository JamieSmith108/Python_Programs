"""Keep the football competitions and safe ESPN request settings together."""

ESPN_API_ROOT = "https://site.api.espn.com/apis/site/v2/sports/soccer"
ESPN_STANDINGS_API_ROOT = "https://site.api.espn.com/apis/v2/sports/soccer"
ESPN_API_HOST = "site.api.espn.com"
ESPN_IMAGE_HOST = "a.espncdn.com"
REQUEST_TIMEOUT_SECONDS = 15
MAX_REPLY_SIZE_BYTES = 5_000_000
MAX_IMAGE_SIZE_BYTES = 2_000_000
ALL_TEAMS_LABEL = "All teams in this league"
LEAGUE_SELECTION_PROMPT = "Please Select League"

# The key is what people see in the league list. The value is ESPN's league code.
FOOTBALL_LEAGUES = {
    "English Premier League": "eng.1",
    "English Championship": "eng.2",
    "English League One": "eng.3",
    "English League Two": "eng.4",
    "English National League": "eng.5",
    "Scottish Premiership": "sco.1",
    "Scottish Championship": "sco.2",
    "Scottish League One": "sco.3",
    "Scottish League Two": "sco.4",
    "Irish Premier Division": "irl.1",
    "Northern Irish Premiership": "nir.1",
    "Spanish LaLiga": "esp.1",
    "German Bundesliga": "ger.1",
    "Italian Serie A": "ita.1",
    "French Ligue 1": "fra.1",
    "Major League Soccer (MLS)": "usa.1",
    "UEFA Champions League": "uefa.champions",
    "UEFA Europa League": "uefa.europa",
    "Liga MX": "mex.1",
    "Brazilian Serie A": "bra.1",
}

# These local leagues are selected when someone uses the app for the first time.
DEFAULT_SELECTED_LEAGUES = (
    "English Premier League",
    "English Championship",
    "English League One",
    "English League Two",
    "English National League",
    "Scottish Premiership",
    "Scottish Championship",
    "Scottish League One",
    "Scottish League Two",
    "Irish Premier Division",
    "Northern Irish Premiership",
)

# These headings keep league choices together in the settings window.
LEAGUE_GROUPS = {
    "English leagues": (
        "English Premier League",
        "English Championship",
        "English League One",
        "English League Two",
        "English National League",
    ),
    "Scottish leagues": (
        "Scottish Premiership",
        "Scottish Championship",
        "Scottish League One",
        "Scottish League Two",
    ),
    "Irish and Northern Irish leagues": (
        "Irish Premier Division",
        "Northern Irish Premiership",
    ),
    "Other leagues": (
        "Spanish LaLiga",
        "German Bundesliga",
        "Italian Serie A",
        "French Ligue 1",
        "Major League Soccer (MLS)",
        "UEFA Champions League",
        "UEFA Europa League",
        "Liga MX",
        "Brazilian Serie A",
    ),
}
