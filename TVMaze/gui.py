"""Build the main window and connect its buttons to the program."""

from __future__ import annotations

from threading import Thread
import tkinter as tk
from tkinter import messagebox, ttk
from types import TracebackType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import ImageTk

from application_logging import (
    log_application_error,
    start_application_logging,
    stop_application_logging,
)
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
from helpers import make_photo_image, make_scrollable_frame
from presentation import format_program_details
from settings_window import SettingsWindow
from tvmaze_api import (
    ProgramDetails,
    ProgramChoice,
    ProgramNotFoundError,
    TVMazeError,
    find_program_choices,
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
        self.choice_window: tk.Toplevel | None = None
        self.choice_images: list[ImageTk.PhotoImage] = []

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
        start_application_logging(new_settings.application_log_path)
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
        try:
            Thread(
                target=self.find_program,
                args=(program_name,),
                daemon=True,
            ).start()
        except (OSError, RuntimeError) as error:
            log_application_error("starting a TV program search", error)
            self.finish_with_message(
                "The program could not start the search. "
                "Please try again or check the application log."
            )

    def find_program(self, program_name: str) -> None:
        """Ask TVMaze for a program and send the answer back to the window."""
        try:
            program_choices = find_program_choices(program_name, self.settings)
        except (ProgramNotFoundError, TVMazeError) as error:
            log_application_error("searching for a TV program", error)
            error_message = str(error)
            self.window.after(
                0,
                lambda: self.finish_with_message(error_message),
            )
            return
        except (OSError, UnicodeError, ValueError) as error:
            log_application_error("looking up a TV program", error)
            self.window.after(
                0,
                lambda: self.finish_with_message(
                    "Something went wrong inside the program. "
                    "Please check the application log."
                ),
            )
            return

        self.window.after(
            0,
            lambda: self.finish_with_choices(program_choices),
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

    def finish_with_choices(self, program_choices: list[ProgramChoice]) -> None:
        """Show a picker only when the search found same-name programs."""
        if len(program_choices) == 1:
            self.finish_with_program(program_choices[0].program)
            return

        if not program_choices:
            self.finish_with_message("TVMaze did not return any matching programs.")
            return

        self.show_program_choice_popup(program_choices)

    def show_program_choice_popup(
        self,
        program_choices: list[ProgramChoice],
    ) -> None:
        """Show pictures and years so a person can choose the right show."""
        popup = tk.Toplevel(self.window)
        self.choice_window = popup
        self.choice_images.clear()
        popup.title("Choose a TV program")
        popup.geometry("560x560")
        popup.minsize(420, 320)
        popup.transient(self.window)
        popup.protocol("WM_DELETE_WINDOW", self.close_program_choice_popup)

        ttk.Label(
            popup,
            text="More than one program has this name. Click its picture:",
            wraplength=520,
        ).pack(anchor="w", padx=12, pady=12)

        choice_area = ttk.Frame(popup)
        choice_area.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        _, choices_frame = make_scrollable_frame(choice_area)

        for program_choice in program_choices:
            self.add_program_choice(
                choices_frame,
                popup,
                program_choice,
            )

        popup.grab_set()
        self.status_message.set("Choose a program in the new window.")

    def add_program_choice(
        self,
        choices_frame: ttk.Frame,
        popup: tk.Toplevel,
        program_choice: ProgramChoice,
    ) -> None:
        """Add one clickable picture and its name and years to the picker."""
        choice_row = ttk.Frame(choices_frame, padding=8)
        choice_row.pack(fill="x", pady=4)
        image_text = "No picture\navailable"
        choice_image = None
        if program_choice.program.image_data is not None:
            try:
                choice_image = make_photo_image(
                    program_choice.program.image_data,
                    (90, 125),
                )
                self.choice_images.append(choice_image)
                image_text = ""
            except (ImportError, OSError, ValueError) as error:
                log_application_error("preparing a program choice picture", error)

        picture_label = ttk.Label(
            choice_row,
            image=choice_image,
            text=image_text,
            compound="center",
            width=14,
            anchor="center",
            relief="groove",
            cursor="hand2",
        )
        picture_label.pack(side="left", padx=(0, 12))
        picture_label.bind(
            "<Button-1>",
            lambda event: self.choose_program(program_choice, popup, event),
        )

        text_frame = ttk.Frame(choice_row)
        text_frame.pack(side="left", fill="x", expand=True)
        ttk.Label(
            text_frame,
            text=program_choice.program.fields.get("name", "Unnamed program"),
            font=("", 11, "bold"),
            wraplength=370,
        ).pack(anchor="w")
        ttk.Label(
            text_frame,
            text=program_choice.years_ran,
        ).pack(anchor="w", pady=(6, 0))

    def choose_program(
        self,
        program_choice: ProgramChoice,
        popup: tk.Toplevel,
        event: tk.Event | None = None,
    ) -> None:
        """Close the picker and show the full details for the chosen show."""
        del event
        popup.destroy()
        self.choice_window = None
        self.choice_images.clear()
        self.finish_with_program(program_choice.program)

    def close_program_choice_popup(self) -> None:
        """Close the picker without choosing and allow another search."""
        if self.choice_window is not None:
            self.choice_window.destroy()
            self.choice_window = None
        self.choice_images.clear()
        self.search_button.configure(state="normal")
        self.status_message.set("Choose a program to see its details.")

    def show_poster(self, picture_data: bytes | None) -> None:
        """Display the downloaded picture, small enough to fit in the window."""
        if picture_data is None:
            self.poster_label.configure(image="", text="")
            self.poster_image = None
            return

        try:
            self.poster_image = make_photo_image(picture_data, (220, 300))
        except (ImportError, OSError, ValueError) as error:
            log_application_error("displaying a downloaded show picture", error)
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
    window.report_callback_exception = report_window_callback_error

    try:
        settings = load_settings()
    except SettingsError as error:
        log_startup_settings_problem(window, error)
        return

    try:
        start_application_logging(settings.application_log_path)
    except (OSError, UnicodeError, ValueError) as error:
        messagebox.showerror(
            "Application log could not be started",
            "The program could not create its application log, so it cannot "
            "save a record of this problem. Check that the log folder exists "
            "and that you are allowed to write to it.\n\n"
            f"Details: {error}",
            parent=window,
        )
        window.destroy()
        return

    try:
        start_api_activity_logging(settings.api_activity_log_path)
    except Exception as error:
        log_application_error("starting a chosen log file", error)
        messagebox.showerror(
            "A log file could not be started",
            "The program could not open one of its log files. Check that the "
            "folder exists and that you are allowed to write to it.\n\n"
            f"Details: {error}",
            parent=window,
        )
        stop_api_activity_logging()
        stop_application_logging()
        window.destroy()
        return

    try:
        ProgramFinderWindow(window, settings)
        window.mainloop()
    except Exception as error:
        log_application_error("running the main program window", error)
        messagebox.showerror(
            "The program ran into a problem",
            "The program could not continue. Please check the application log.",
            parent=window,
        )
    finally:
        stop_api_activity_logging()
        stop_application_logging()


def log_startup_settings_problem(window: tk.Tk, problem: SettingsError) -> None:
    """Use the default log to record why saved settings could not be loaded."""
    try:
        start_application_logging(AppSettings().application_log_path)
        log_application_error("loading the saved settings", problem)
    except (OSError, UnicodeError, ValueError) as log_problem:
        messagebox.showerror(
            "Settings could not be loaded",
            f"{problem}\nThe application log could not be started: {log_problem}",
            parent=window,
        )
    else:
        messagebox.showerror(
            "Settings could not be loaded",
            f"{problem}\nThe problem was written to the default application log.",
            parent=window,
        )
    finally:
        stop_application_logging()
        window.destroy()


def report_window_callback_error(
    error_type: type[BaseException],
    error_value: BaseException,
    error_traceback: TracebackType | None,
) -> None:
    """Write down an unexpected error raised while a window action runs."""
    del error_type, error_traceback
    log_application_error("running a window action", error_value)
    messagebox.showerror(
        "The program ran into a problem",
        "An unexpected problem happened during a window action. "
        f"Problem details: {type(error_value).__name__}: {error_value}\n\n"
        "The details were also saved in the application log.",
    )
