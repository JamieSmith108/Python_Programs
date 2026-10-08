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
   or choose one team to see that team's season schedule. Selecting the choice
   loads the latest match information automatically.
4. Use the **Exit** button at the bottom of the window to close the program.

When ESPN supplies the image addresses, the selected league badge appears to
the right of the league menu and the selected team's badge appears beside the
team menu. Choosing **All teams in this league** clears the team badge. Badge
images are downloaded securely from ESPN and made smaller to fit the window.

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
- `config.py` contains the supported league names and ESPN request limits.
- `log_settings.py` stores and checks the paths chosen for the log files.
- `logging_service.py` writes the logs and checks their SHA-256 checksums.
- `run_tests.py` runs the tests and saves the full results in the testing log.
- `test_runner.py` shares the test-running function with the settings window.
- `tests` contains automatic checks for data reading, logging, and errors.

## Logs and settings

The program uses Python's standard `logging` package. The cog button in the
top-right opens the settings window. From there you can choose a path for each
log, open a log in a read-only viewer, or run the tests and save their full
results.

The default settings file is stored outside the program folder at:

```text
%APPDATA%\FootballMonitor\settings.json
```

The default log files are also stored outside the program folder, under:

```text
%LOCALAPPDATA%\FootballMonitor\Logs
```

The three logs record different information:

- `API_communications_log.txt` stores each ESPN request type, requested
  address, complete reply when it fits the safe response limit, HTTP status,
  and a unique correlation ID. If ESPN sends more than the safe limit, the
  log marks that the reply was truncated.
- `application_log.txt` records important activity and errors. Error entries
  say where the problem happened, what caused it, and what the user can do.
- `testing_log.txt` stores the full test output from tests run with the
  settings window or the command below.

The log viewer is read-only, and log files are marked read-only between app
writes. A separate `log_checksums.json` SHA-256 checksum file is kept alongside
the external settings. The program checks the checksum before displaying or
adding to a log. If a log has changed since its last saved checksum, it shows a
warning and does not add new entries to that changed file. A checksum is a
tamper warning, not protection against someone who can change both the log and
the checksum file.

## How testing works

Tests check that the program reads team names and match details correctly,
builds the right ESPN requests, explains unsafe or unreadable web replies,
checks external log settings, and detects changed log files. The tests use
sample replies saved in the test code, so they do not need an internet
connection and never contact ESPN. They do not change the real app's data.

To run the tests and save the complete results in `testing_log.txt`, open
PowerShell in the project folder and run:

```powershell
python run_tests.py
```

PowerShell prints each test name and whether it passed. The same complete
output is saved in the configured testing log. If a test fails, its output
includes the test name and the expected and actual results.

## ESPN data

The program uses ESPN's publicly reachable football data endpoints. This is an
unofficial client: ESPN may change or limit these endpoints, and information
availability can vary by league. Match details are shown as ESPN supplies
them.