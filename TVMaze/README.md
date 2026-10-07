# TVMaze Show Finder

TVMaze Show Finder is a small desktop program. Type a TV show name, and it
looks up the show using the free TVMaze website. The program shows the details
in a window and can display the show's picture.

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

3. Install the picture library:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Start the program:

   ```powershell
   python main.py
   ```

5. Type a show name and choose **Find program**. You can also press Enter.

The search runs while the window stays open and responsive. TVMaze usually
returns its closest match. If the result is not the show you meant, try a
different spelling or a longer show name.

## Use the buttons

- **Find program** searches for the name in the box.
- **⚙** opens Settings.
- **Exit** closes the program.

When the **Show images** field is selected, the show picture appears above the
details. If TVMaze has no picture, the rest of the show details still appear.

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

## Change other settings

The Settings window also lets you change:

- The main window title
- The main window width and height
- The smallest size the main window can be
- The TVMaze search address
- How long the program waits for a reply, in seconds

Choose **Save settings** to remember your choices. The window title and size
change at once. The search address, wait time, and selected details are used
for the next search.

Your saved choices go into `settings.json` beside the program. You can change
settings in the window; you do not need to edit this file by hand. The default
settings and the list of available TVMaze fields are in `config.py`.

## What each program file does

- `main.py` starts the desktop program.
- `gui.py` builds the main window and handles searching, pictures, and Exit.
- `settings_window.py` builds the separate Settings window.
- `tvmaze_api.py` asks TVMaze for a show and makes its answer readable.
- `presentation.py` puts the chosen show details into a clear list.
- `helpers.py` contains small text-cleaning and label-making functions.
- `config.py` holds default settings and the list of available show details.
- `settings.json` stores the choices you saved in the Settings window.
- `tests` contains checks that help make sure the program works.
- `requirements.txt` lists the extra library needed to display pictures.

## If something goes wrong

- **The program cannot find a show:** Check the spelling and try again.
- **The search cannot connect:** Check your internet connection and try again.
- **Pictures do not appear:** Install the requirements with
  `python -m pip install -r requirements.txt`, then restart the program.
- **Settings will not save:** Check that all number boxes contain whole
  numbers, the window is not smaller than its minimum size, and at least one
  show detail is checked.
- **The program says settings cannot be loaded:** Close the program and move
  `settings.json` to another folder. The next start will use the default
  settings. You can then choose your settings again in the window.

TVMaze supplies the show information and pictures. The data may be missing or
out of date for some shows.