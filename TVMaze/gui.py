"""Build the main window and connect its buttons to the program."""

from io import BytesIO
from threading import Thread
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from api_activity_logging import (
    start_api_activity_logging,
    stop_api_activity_logging,
)
from config import (
    AppSettings,
    EXIT_BUTTON_TEXT,
    SEARCH_BUTTON_TEXT,
    SEARCH_LABEL,
    SettingsError,
    WAITING_MESSAGE,
    WELCOME_MESSAGE,
    load_settings,
)
from presentation import format_program_details
from settings_window import SettingsWindow
from tvmaze_api import (
    ProgramDetails,
    ProgramNotFoundError,
    TVMazeError,
    find_program_details,
)


class ProgramFinderWindow:
    """Show the search box, settings button, results, and Exit button."""

    def __init__(self, window: tk.Tk, settings: AppSettings) -> None:
        """Set up the main window and remember the saved settings."""
        self.window = window
        self.settings = settings
        self.search_name = tk.StringVar()
        self.status_message = tk.StringVar(value=WELCOME_MESSAGE)
        self.poster_image: ImageTk.PhotoImage | None = None

        self.set_window_size()
        self.build_window()

    def set_window_size(self) -> None:
        """Set the window title and size from the saved settings."""
        self.window.title(self.settings.window_title)
        self.window.geometry(
            f"{self.settings.window_width}x{self.settings.window_height}"
        )
        self.window.minsize(
            self.settings.minimum_window_width,
            self.settings.minimum_window_height,
        )

    def build_window(self) -> None:
        """Place the search controls and results in the main window."""
        main_frame = ttk.Frame(self.window, padding=16)
        main_frame.pack(fill="both", expand=True)

        self.add_exit_button(main_frame)
        self.add_status_message(main_frame)
        self.add_settings_button(main_frame)
        self.add_search_box(main_frame)

        self.poster_label = ttk.Label(main_frame)
        self.poster_label.pack(pady=(0, 8))

        self.result_box = tk.Text(main_frame, wrap="word", height=18)
        self.result_box.pack(fill="both", expand=True)
        self.show_message(WELCOME_MESSAGE)

    def add_exit_button(self, parent: ttk.Frame) -> None:
        """Put a button at the bottom that closes the program."""
        ttk.Button(
            parent,
            text=EXIT_BUTTON_TEXT,
            command=self.window.destroy,
        ).pack(side="bottom", anchor="center", pady=(10, 0))

    def add_status_message(self, parent: ttk.Frame) -> None:
        """Show a short message under the results."""
        ttk.Label(
            parent,
            textvariable=self.status_message,
        ).pack(side="bottom", anchor="w", pady=(8, 0))

    def add_settings_button(self, parent: ttk.Frame) -> None:
        """Put the cog button at the top-right of the window."""
        settings_row = ttk.Frame(parent)
        settings_row.pack(fill="x")
        ttk.Button(
            settings_row,
            text="⚙",
            width=3,
            command=self.open_settings,
        ).pack(side="right")

    def add_search_box(self, parent: ttk.Frame) -> None:
        """Add a box and button for searching by program name."""
        ttk.Label(parent, text=SEARCH_LABEL).pack(anchor="w")
        search_row = ttk.Frame(parent)
        search_row.pack(fill="x", pady=(6, 12))

        search_box = ttk.Entry(search_row, textvariable=self.search_name)
        search_box.pack(side="left", fill="x", expand=True)
        search_box.bind("<Return>", self.start_search)

        self.search_button = ttk.Button(
            search_row,
            text=SEARCH_BUTTON_TEXT,
            command=self.start_search,
        )
        self.search_button.pack(side="right", padx=(8, 0))

    def open_settings(self) -> None:
        """Open the separate window for changing program settings."""
        SettingsWindow(self.window, self.settings, self.apply_settings)

    def apply_settings(self, new_settings: AppSettings) -> None:
        """Use the saved settings and update the main window."""
        start_api_activity_logging(new_settings.api_activity_log_path)
        self.settings = new_settings
        self.set_window_size()
        self.status_message.set("Settings saved.")

    def start_search(self, event: tk.Event | None = None) -> None:
        """Check the search box, then look up the program in the background."""
        del event
        program_name = self.search_name.get().strip()
        if not program_name:
            self.show_message("Please enter the name of a TV program.")
            return

        self.search_button.configure(state="disabled")
        self.status_message.set(WAITING_MESSAGE)
        self.show_message(WAITING_MESSAGE)
        Thread(
            target=self.find_program,
            args=(program_name,),
            daemon=True,
        ).start()

    def find_program(self, program_name: str) -> None:
        """Ask TVMaze for a program and send the answer back to the window."""
        try:
            program_details = find_program_details(program_name, self.settings)
        except (ProgramNotFoundError, TVMazeError) as error:
            error_message = str(error)
            self.window.after(
                0,
                lambda: self.finish_with_message(error_message),
            )
            return

        self.window.after(
            0,
            lambda: self.finish_with_program(program_details),
        )

    def finish_with_message(self, message: str) -> None:
        """Show an error or hint and allow another search."""
        self.show_message(message)
        self.status_message.set(message)
        self.search_button.configure(state="normal")

    def finish_with_program(self, program: ProgramDetails) -> None:
        """Show the program information and allow another search."""
        if "image" in self.settings.selected_show_fields:
            self.show_poster(program.image_data)
        else:
            self.show_poster(None)

        self.show_message(
            format_program_details(program, self.settings.selected_show_fields)
        )
        self.status_message.set(f"Found: {program.fields.get('name', 'program')}")
        self.search_button.configure(state="normal")

    def show_poster(self, picture_data: bytes | None) -> None:
        """Display the downloaded picture, small enough to fit in the window."""
        if picture_data is None:
            self.poster_label.configure(image="", text="")
            self.poster_image = None
            return

        try:
            picture = Image.open(BytesIO(picture_data))
            picture.thumbnail((220, 300))
            self.poster_image = ImageTk.PhotoImage(picture)
        except (OSError, ValueError):
            self.poster_label.configure(
                image="",
                text="The show image could not be displayed.",
            )
            self.poster_image = None
            return

        self.poster_label.configure(image=self.poster_image, text="")

    def show_message(self, message: str) -> None:
        """Replace the text shown in the results box."""
        self.result_box.configure(state="normal")
        self.result_box.delete("1.0", "end")
        self.result_box.insert("1.0", message)
        self.result_box.configure(state="disabled")


def start_program() -> None:
    """Load saved settings and open the TVMaze program window."""
    window = tk.Tk()
    try:
        settings = load_settings()
        start_api_activity_logging(settings.api_activity_log_path)
    except OSError as error:
        messagebox.showerror(
            "API issue log could not be started",
            f"The program could not create its API troubleshooting log: {error}",
            parent=window,
        )
        window.destroy()
        return

    except SettingsError as error:
        messagebox.showerror("Settings could not be loaded", str(error), parent=window)
        window.destroy()
        return

    ProgramFinderWindow(window, settings)
    window.mainloop()
    stop_api_activity_logging()
