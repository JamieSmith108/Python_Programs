# TVMaze Show Finder

This small program looks up a TV program on TVMaze and shows the details in a
window.

## What you need

- Python 3.10 or newer
- An internet connection

The program uses Python's built-in tools. You do not need to install extra
packages.

## Start the program

1. Open a terminal in this folder.
2. Run:

   ```powershell
   python main.py
   ```

3. Type a TV program name in the box.
4. Choose **Find program**, or press Enter.

The program shows the information TVMaze has for the closest matching show.
If TVMaze cannot find it, check the spelling and try again.

## How the files fit together

- `main.py` starts the program.
- `gui.py` builds the window and handles button presses.
- `tvmaze_api.py` asks TVMaze for a show and picks out its details.
- `helpers.py` holds small functions that other files can reuse.
- `config.py` keeps the settings and screen messages in one place.

## Change the settings

Open `config.py` to change the window size, title, connection timeout, or
messages shown by the program.