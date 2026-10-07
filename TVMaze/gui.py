"""Create the screen and connect it to the TVMaze search."""

from threading import Thread
import tkinter as tk
from tkinter import ttk

from config import (
    MINIMUM_WINDOW_HEIGHT,
    MINIMUM_WINDOW_WIDTH,
    SEARCH_BUTTON_TEXT,
    SEARCH_LABEL,
    WAITING_MESSAGE,
    WELCOME_MESSAGE,
    WINDOW_SIZE,
    WINDOW_TITLE,
)
from helpers import read_text
from tvmaze_api import ShowDetails, ShowNotFoundError, TVMazeError, search_for_show


class ShowFinderWindow:
    """Build the screen and respond when someone searches for a show."""

    def __init__(self, window: tk.Tk) -> None:
        """Set up the search box, button, and results area."""
        self.window = window
        self.window.title(WINDOW_TITLE)
        self.window.geometry(WINDOW_SIZE)
        self.window.minsize(MINIMUM_WINDOW_WIDTH, MINIMUM_WINDOW_HEIGHT)

        self.search_text = tk.StringVar()
        self.search_button: ttk.Button
        self.result_text: tk.Text
        self.status_text = tk.StringVar(value=WELCOME_MESSAGE)

        self.build_screen()

    def build_screen(self) -> None:
        """Place the search controls and results area in the window."""
        main_frame = ttk.Frame(self.window, padding=16)
        main_frame.pack(fill="both", expand=True)

        search_label = ttk.Label(main_frame, text=SEARCH_LABEL)
        search_label.pack(anchor="w")

        search_row = ttk.Frame(main_frame)
        search_row.pack(fill="x", pady=(6, 12))

        search_box = ttk.Entry(search_row, textvariable=self.search_text)
        search_box.pack(side="left", fill="x", expand=True)
        search_box.bind("<Return>", self.start_search)

        self.search_button = ttk.Button(
            search_row,
            text=SEARCH_BUTTON_TEXT,
            command=self.start_search,
        )
        self.search_button.pack(side="left", padx=(8, 0))

        self.result_text = tk.Text(main_frame, wrap="word", height=18)
        self.result_text.pack(fill="both", expand=True)
        self.result_text.insert("1.0", WELCOME_MESSAGE)
        self.result_text.configure(state="disabled")

        status_label = ttk.Label(main_frame, textvariable=self.status_text)
        status_label.pack(anchor="w", pady=(8, 0))

    def start_search(self, event: tk.Event | None = None) -> None:
        """Check the search text and start looking without freezing the window."""
        del event
        search_name = self.search_text.get().strip()
        if not search_name:
            self.show_message("Please enter the name of a TV program.")
            return

        self.search_button.configure(state="disabled")
        self.status_text.set(WAITING_MESSAGE)
        self.show_message(WAITING_MESSAGE)
        search_thread = Thread(
            target=self.look_up_show,
            args=(search_name,),
            daemon=True,
        )
        search_thread.start()

    def look_up_show(self, search_name: str) -> None:
        """Look up the show, then safely send the result back to the screen."""
        try:
            show_details = search_for_show(search_name)
        except (ShowNotFoundError, TVMazeError) as error:
            message = str(error)
            self.window.after(0, lambda: self.finish_with_message(message))
        else:
            self.window.after(0, lambda: self.finish_with_show(show_details))

    def finish_with_message(self, message: str) -> None:
        """Show a search message and let the person search again."""
        self.show_message(message)
        self.status_text.set(message)
        self.search_button.configure(state="normal")

    def finish_with_show(self, show_details: ShowDetails) -> None:
        """Show the program details and let the person search again."""
        self.show_message(format_show_details(show_details))
        self.status_text.set(f"Found: {show_details.name}")
        self.search_button.configure(state="normal")

    def show_message(self, message: str) -> None:
        """Replace the words currently shown in the results area."""
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", message)
        self.result_text.configure(state="disabled")


def format_show_details(show_details: ShowDetails) -> str:
    """Turn the show details into a clear list for the results area."""
    details = [
        ("Program", show_details.name),
        ("Type", show_details.show_type),
        ("Language", show_details.language),
        ("Genres", show_details.genres),
        ("Status", show_details.status),
        ("First shown", show_details.premiered),
        ("Last shown", show_details.ended),
        ("Episode length", add_minutes(show_details.runtime)),
        ("Rating", show_details.rating),
        ("TV channel", show_details.channel),
        ("Schedule", show_details.schedule),
        ("Official website", show_details.official_site),
        ("Summary", show_details.summary),
    ]
    return "\n\n".join(f"{label}: {value}" for label, value in details)


def add_minutes(runtime: str) -> str:
    """Add minutes after an episode length when TVMaze provides one."""
    if runtime.isdigit():
        return f"{runtime} minutes"

    return read_text(runtime)


def run_app() -> None:
    """Open the program window and keep it running until it is closed."""
    window = tk.Tk()
    ShowFinderWindow(window)
    window.mainloop()
