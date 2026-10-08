# TVMaze Show Finder

TVMaze Show Finder is a small desktop program. Type a TV show name, and it
looks up the show using the free TVMaze website. The program shows the details
in a window and can display the show's picture. The TVMaze API is the service
the program uses to ask the TVMaze website for show information.

## What you need

- Python 3.10 or newer
- An internet connection
- Pillow, a small library that opens picture files

You do not need a TVMaze account or an API key.

## Install and start the program

1. Open PowerShell or another terminal.
2. Move into the TVMaze folder. For example:

   ```powershell
   cd "C:\Users\Admin\Desktop\Python_Programs\TVMaze"
   ```

3. Make a private Python environment for this program:

   ```powershell
   python -m venv .venv
   ```

4. Turn on that environment:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks the activation script, you can use the environment's
   Python directly instead: `.venv\Scripts\python.exe`.

5. Install the picture library inside the environment:

   ```powershell
   python -m pip install -r requirements.txt
   ```

6. Start the program:

   ```powershell
   python main.py
   ```

7. Type a show name and choose **Find program**. You can also press Enter.

The `.venv` folder belongs to this project and keeps its libraries separate
from other Python programs on your computer. When the environment is turned
on, `python main.py` uses this program's private Python and installed
libraries.

The search runs while the window stays open and responsive. If TVMaze finds
more than one program with exactly the same name, a choice window appears.
Each choice shows its name, the years it ran, and a small picture. Click the
picture for the program you want to see its full details in the main window.
If a picture is not available, click the words where the picture would be.
When there is only one exact name match, its details appear straight away.
Similar names are not treated as duplicate names. If there is no exact name
match, the highest-ranked result from TVMaze is shown.

## Use the buttons

- **Find program** searches for the name in the box.
- **⚙** opens Settings.
- **Exit** closes the program.

When the **Show images** field is selected, the show picture appears above the
details. If TVMaze has no picture, the rest of the show details still appear.
Pictures in the duplicate-name choice window are shown even when **Show
images** is not selected, so you can tell the choices apart.

## Choose which details to show

1. Choose the **⚙** button in the top-right corner.
2. Find **Choose the show details to display**.
3. Check the details you want. Uncheck the details you do not want.
4. Use the list's scroll bar to see every available detail.
5. Leave at least one detail checked.
6. Choose **Save settings**.

The next search uses your selected fields. TVMaze's nested information is
shown with readable labels, not JSON braces and quotes. For example, a rating
appears as “8.3 out of 10,” and a schedule can appear as “Sunday at 8:00 PM.”

The available details are:

- Show ID and TVMaze page
- Program name, program type, language, genres, and status
- Episode length and average episode length
- First shown and last shown dates
- Official website and schedule
- Rating and match weight
- TV network and web channel
- DVD country and external database IDs
- Show images and summary
- Last updated date and related episode links

## Change other settings

The Settings window also lets you change:

- The main window title
- The main window width and height
- The smallest size the main window can be
- The TVMaze search address
- How long the program waits for a reply, in seconds
- The full path where the API issue-tracking log is saved
- The full path where the application problem log is saved

Choose **Save settings** to remember your choices. The window title and size
change at once. The search address, wait time, and selected details are used
for the next search. Enter a full file path for the API issue-tracking log,
such as
`C:\Users\YourName\AppData\Local\TVMazeShowFinder\API_activity_logging.log`.
Enter a full file path for the application log, such as
`C:\Users\YourName\AppData\Local\TVMazeShowFinder\application_log`. Both log
files must be saved outside the program folder and must use different file
paths.

The Settings window has **View API issue log** and **View application log**
buttons. Each button shows the file at the path currently in its setting box
in a read-only window inside the program. You can select and copy the notes,
but you cannot change them there. If you try to type, delete, paste, or cut,
the program warns you and blocks the change. If the log has not been created
yet, the program explains that it cannot open it. Save the settings with that
log path first; the program creates the log when it starts using the saved
location.

The read-only rule applies to the viewer inside this program. The log files
must still be writable by the program so it can add new notes. Opening the
file separately in another program is outside this protection.

The program also saves a `.sha256` checksum file beside each log. When you
open a log in Settings, the program compares the log with its saved checksum.
If the contents do not match, the viewer shows a warning that the log may have
been changed outside the program. Normal notes written by the program update
the checksum automatically.

This check notices changes to the log contents; it cannot tell that someone
tried to edit a file if the edit was blocked or did not change its contents.
It is a warning aid, not a security lock: someone who changes both the log
and its checksum can avoid this simple check. Older log files without a
checksum get a starting checksum the first time the updated program uses
them, so changes made before that first use cannot be detected.
After the program notices an outside change, it keeps the old checksum rather
than replacing it with a checksum for the changed contents.

Your saved choices go into `settings.json` beside the program. You can change
settings in the window; you do not need to edit this file by hand. The default
settings and the list of available TVMaze fields are in `config.py`. The
program also understands the older `activity_log_path` setting, so upgrading
will keep using the log location you already chose. When you save settings,
the program writes the clearer `api_activity_log_path` name.

## How the program keeps website requests safe

The program only contacts the official TVMaze show-search website at
`api.tvmaze.com` and the TVMaze picture website at `static.tvmaze.com`. The
search address in Settings must be the official secure show-search address.
The program uses TVMaze's matching-list address to find same-name choices.
Picture addresses must use the TVMaze picture website and an image file type
the program understands. Other websites, unencrypted addresses, look-alike
addresses, and unexpected address details are rejected before the program
tries to connect.

The program also refuses website redirects. An approved TVMaze address cannot
send the program on to a different website. A show name must not be empty or
longer than 200 characters, and its website address is also size-limited. The
wait limit must be from 1 to 120 seconds.
API replies are limited to 5 megabytes; picture replies are limited to 10
megabytes. Replies must have the expected kind of content: JSON for show
details and JPEG, PNG, or WebP for pictures. Picture addresses returned by
TVMaze are checked again before the program opens them. If a reply fails one
of these checks, the program records the issue in the API issue-tracking log
and explains the problem without showing unusable information.

## What each program file does

- `main.py` starts the desktop program.
- `gui.py` builds the main window and handles searching, pictures, and Exit.
- `settings_window.py` builds the separate Settings window.
- `tvmaze_api.py` asks TVMaze for matching shows, makes their answers readable,
  and finds the years each show ran.
- `presentation.py` puts the chosen show details into a clear list.
- `helpers.py` contains shared text-cleaning, label-making, picture-resizing
  and display, scrollable-list, safe-address, and logger-cleanup functions
  used by other files.
- `api_activity_logging.py` records API request and reply details to help find
  API problems.
- `application_logging.py` records errors and problems that happen inside the
  program.
- `config.py` holds default settings and the list of available show details.
- `settings.json` stores the choices you saved in the Settings window.
- The API issue-tracking log and the application log are saved at the
  locations shown in Settings, outside the program folder.
- `tests` contains checks that help make sure the program works.
- `requirements.txt` lists the extra library needed to display pictures.

The Settings list and the duplicate-program picker use the same shared
scrollable-list helper. The main results and duplicate-program picker also
use one helper to resize pictures and prepare them for display. Both log files
use the same shared log-cleanup helper. Tests that read saved log notes use
one shared helper to flush and read the file. This keeps those repeated jobs
in one place, so a future change can be made once and used by every part of
the program.

## Read the API issue-tracking log

This is a special log for understanding problems when the program talks to the
TVMaze API. It is not a general record of everything a person does in the
program. The log location is shown in Settings. By default, the log is saved
in your Windows user application-data folder as
`%LOCALAPPDATA%\TVMazeShowFinder\API_activity_logging.log`. This keeps it out
of the program folder. You can choose another full file path in Settings, as
long as it is outside the program folder.

The log records when the program starts a TVMaze API request, what HTTP status
the server returns, how long the request takes, how many bytes come back, and
helpful server details such as request or trace IDs. If an API connection or
reply fails, it records the type of problem and the explanation. The same
search reference is attached to the show's details request and its picture
request, making it easier to find the notes for one search.

The log uses plain-English messages. When it reaches about one megabyte, it
starts a fresh file and keeps up to three older log files.

For privacy, the log keeps only a short list of useful API response headers.
It does not save cookies, authorization details, or the contents of TVMaze
responses. The request address includes the name typed into the search box.

## Read the application log

The application log records problems inside the program, such as an unexpected
error while the window is running, a problem displaying a downloaded picture,
or trouble loading and saving settings. It includes the time, the kind of
error, a plain-English explanation, and the place in the code where the error
happened. This helps explain problems that are not caused by the TVMaze API.

The log is saved at the full path shown in Settings. The default file is named
`application_log` and is kept in
`%LOCALAPPDATA%\TVMazeShowFinder\application_log`, outside the program folder.
The file grows to about one megabyte before it is rotated; up to three older
files are kept. The application log does not replace the API issue-tracking
log: use the API log for web requests and replies, and the application log for
problems inside the program.

Both logs may include error details that help diagnose a problem. Do not share
the files publicly if their contents include information you want to keep
private.

## If something goes wrong

- **The program cannot find a show:** Check the spelling and try again.
- **The program cannot find or connect to a show:** A clear message appears in
  the program. The problem and its technical details are also written to the
  application log. Check the spelling or internet connection, then try again.
- **The TVMaze address is rejected:** In Settings, use
  `https://api.tvmaze.com/singlesearch/shows`. Other websites are not allowed.
  The problem is shown in the program and written to the application log.
- **The API issue-tracking log cannot be created:** Check that the chosen
  folder exists or can be created, that you have permission to write there,
  and that the log path is outside the program folder. The program shows a
  message and records the problem in the application log.
- **The application log cannot be created:** Check that its folder can be
  created, that you have permission to write there, and that its path is
  outside the program folder. The program shows a message explaining that it
  cannot save this problem to the application log until that log can be made.
- **The log viewer warns about an outside change:** The log no longer matches
  its saved checksum. Keep a copy if you need to investigate it. The program
  still lets you read and copy the log, but it does not edit the old checksum
  to hide the change. The warning is also recorded in the application log.
- **Pictures do not appear:** Install the requirements with
  `python -m pip install -r requirements.txt`, then restart the program. The
  rest of the show details stay available; picture download or display
  problems are recorded in the application log.
- **Settings will not save:** Check that all number boxes contain whole
  numbers, the window is not smaller than its minimum size, and at least one
  show detail is checked. The program explains what needs fixing and records
  the problem in the application log.
- **A search cannot start:** The program explains that the search could not be
  started, records the technical problem in the application log, and makes the
  search button available again.
- **The program says settings cannot be loaded:** Close the program and move
  `settings.json` to another folder. The next start will use the default
  settings. This can also help if the file contains unreadable text. You can
  then choose your settings again in the window. The program shows a message
  and records why it could not read the saved settings in the default
  application log, if that log can be created.

If the program hits an unexpected problem while a window action is running,
it shows the error type and details and records the full problem in the
application log. If a log cannot be started, the program explains that it
cannot save the problem to that log and tells you to check its folder and
permissions.

TVMaze supplies the show information and pictures. The data may be missing or
out of date for some shows.