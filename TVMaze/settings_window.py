"""Show a separate window for changing the program settings."""

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from config import AppSettings, SHOW_FIELD_OPTIONS, SettingsError, save_settings


class SettingsWindow:
    """Build the settings form and save the choices."""

    def __init__(
        self,
        main_window: tk.Tk,
        current_settings: AppSettings,
        settings_saved: Callable[[AppSettings], None],
    ) -> None:
        """Open the settings form and remember how to save it."""
        self.current_settings = current_settings
        self.settings_saved = settings_saved
        self.window = tk.Toplevel(main_window)
        self.window.title("Settings")
        self.window.geometry("760x740")
        self.window.minsize(680, 650)
        self.window.transient(main_window)
        self.window.grab_set()

        self.setting_boxes: dict[str, tk.StringVar] = {}
        self.field_checks: dict[str, tk.BooleanVar] = {}
        self.build_form()

    def build_form(self) -> None:
        """Place setting boxes, field checkboxes, and save buttons."""
        form = ttk.Frame(self.window, padding=16)
        form.pack(fill="both", expand=True)

        self.add_setting_boxes(form)
        self.add_field_checkboxes(form)
        self.add_form_buttons(form)

    def add_setting_boxes(self, form: ttk.Frame) -> None:
        """Add a labelled text box for each basic program setting."""
        setting_rows = [
            ("Window title", "window_title", self.current_settings.window_title),
            ("Window width", "window_width", str(self.current_settings.window_width)),
            ("Window height", "window_height", str(self.current_settings.window_height)),
            (
                "Minimum window width",
                "minimum_window_width",
                str(self.current_settings.minimum_window_width),
            ),
            (
                "Minimum window height",
                "minimum_window_height",
                str(self.current_settings.minimum_window_height),
            ),
            ("TVMaze API address", "tvmaze_api_url", self.current_settings.tvmaze_api_url),
            (
                "Request timeout (seconds)",
                "request_timeout_seconds",
                str(self.current_settings.request_timeout_seconds),
            ),
        ]

        for row_number, (label_text, setting_name, setting_value) in enumerate(
            setting_rows
        ):
            ttk.Label(form, text=label_text).grid(
                row=row_number,
                column=0,
                sticky="w",
                padx=(0, 12),
                pady=4,
            )
            text_value = tk.StringVar(value=setting_value)
            self.setting_boxes[setting_name] = text_value
            ttk.Entry(form, textvariable=text_value, width=42).grid(
                row=row_number,
                column=1,
                sticky="ew",
                pady=4,
            )

    def add_field_checkboxes(self, form: ttk.Frame) -> None:
        """Add a scrollable list for choosing which show details to display."""
        first_row = len(self.setting_boxes)
        ttk.Label(
            form,
            text="Choose the show details to display:",
        ).grid(row=first_row, column=0, columnspan=2, sticky="w", pady=(12, 4))

        list_frame = ttk.Frame(form)
        list_frame.grid(
            row=first_row + 1,
            column=0,
            columnspan=2,
            sticky="nsew",
        )
        form.columnconfigure(1, weight=1)
        form.rowconfigure(first_row + 1, weight=1)

        canvas = tk.Canvas(list_frame, height=190, highlightthickness=0)
        scroll_bar = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=canvas.yview,
        )
        canvas.configure(yscrollcommand=scroll_bar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll_bar.pack(side="right", fill="y")

        checkboxes = ttk.Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=checkboxes, anchor="nw")
        checkboxes.bind(
            "<Configure>",
            lambda event: canvas.configure(scrollregion=event.widget.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(canvas_window, width=event.width),
        )

        for field_number, (field_name, field_label) in enumerate(SHOW_FIELD_OPTIONS):
            checked = tk.BooleanVar(
                value=field_name in self.current_settings.selected_show_fields
            )
            self.field_checks[field_name] = checked
            ttk.Checkbutton(
                checkboxes,
                text=field_label,
                variable=checked,
            ).grid(
                row=field_number // 2,
                column=field_number % 2,
                sticky="w",
                padx=(0, 18),
                pady=2,
            )

    def add_form_buttons(self, form: ttk.Frame) -> None:
        """Add buttons for saving changes or closing without saving."""
        button_row = ttk.Frame(form)
        button_row.grid(
            row=len(self.setting_boxes) + 2,
            column=0,
            columnspan=2,
            sticky="e",
            pady=(12, 0),
        )
        ttk.Button(
            button_row,
            text="Cancel",
            command=self.window.destroy,
        ).pack(side="right")
        ttk.Button(
            button_row,
            text="Save settings",
            command=self.save,
        ).pack(side="right", padx=(0, 8))

    def make_settings_from_form(self) -> AppSettings:
        """Read the boxes and checked boxes into one settings object."""
        return AppSettings(
            window_title=self.setting_boxes["window_title"].get().strip(),
            window_width=int(self.setting_boxes["window_width"].get()),
            window_height=int(self.setting_boxes["window_height"].get()),
            minimum_window_width=int(
                self.setting_boxes["minimum_window_width"].get()
            ),
            minimum_window_height=int(
                self.setting_boxes["minimum_window_height"].get()
            ),
            tvmaze_api_url=self.setting_boxes["tvmaze_api_url"].get().strip(),
            request_timeout_seconds=int(
                self.setting_boxes["request_timeout_seconds"].get()
            ),
            selected_show_fields=tuple(
                field_name
                for field_name, checked in self.field_checks.items()
                if checked.get()
            ),
        )

    def save(self) -> None:
        """Validate and save the settings, then tell the main window."""
        try:
            new_settings = self.make_settings_from_form()
            save_settings(new_settings)
        except (ValueError, SettingsError) as error:
            messagebox.showerror(
                "Settings not saved",
                str(error),
                parent=self.window,
            )
            return

        self.settings_saved(new_settings)
        self.window.destroy()
