# ESPN Football Monitor

ESPN Football Monitor is a small desktop program for football. It reads
current league, team, fixture, and score information from
ESPN's public data service. It does not make up match details.

## Start the program

You need Python 3.10 or newer and an internet connection.

1. Open PowerShell in the FootballMonitor folder.
2. Start the program:

   ```powershell
   python main.py
   ```

The program uses Python's built-in Tkinter and web libraries. No extra
packages or account are needed.

## Choose a league and team

1. Choose a football league from the first menu.
2. Wait while the program asks ESPN for that league's current team list.
3. Choose **All teams in this league** to see ESPN's current league scoreboard,
   or choose one team to see that team's season schedule.
4. Choose **Refresh football information** to ask ESPN for the latest available
   information.

The program shows fixture times in your computer's local time zone. If there
are no matches to show at that time, it says so rather than inventing results.
Team lists, fixtures, scores, match status, and venue details come from ESPN.

The program currently offers the English Premier League, English Championship,
Spanish LaLiga, German Bundesliga, Italian Serie A, French Ligue 1, Major League
Soccer (MLS), UEFA Champions League, UEFA Europa League, Liga MX, Brazilian Serie A,
and Scottish Premiership.

## If information cannot be loaded

The program shows a clear message if your internet connection is unavailable,
ESPN returns an error, or ESPN sends information the program cannot read.
Check your connection and try refreshing again. Some competitions may have no
matches scheduled at the moment.

## How the program is organised

- `main.py` starts the desktop window.
- `gui.py` builds the window, choices, and match display.
- `football_api.py` requests and reads league, team, and match information.
- `helpers.py` contains shared safe web-request and text-cleaning functions.
- `config.py` contains the supported league names and request limits.
- `tests` contains automatic checks for data reading and error cases.

## How testing works

Tests check that the program reads team names and match details correctly,
builds the right ESPN requests, and explains unsafe or unreadable web replies.
The tests use sample replies saved in the test code, so they do not need an
internet connection and never contact ESPN. They do not change the real app.

To run the tests, open PowerShell in the project folder and run:

```powershell
python -m unittest discover -s tests -v
```

PowerShell prints each test name and whether it passed. If a test fails, its
output includes the test name and the expected and actual results.

## ESPN data

The program uses ESPN's publicly reachable football data endpoints. This is an
unofficial client: ESPN may change or limit these endpoints, and information
availability can vary by league. Match details are shown as ESPN supplies
them.