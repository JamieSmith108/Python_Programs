"""Build the window where people choose a football league and see ESPN data."""

import base64
from collections.abc import Callable
from pathlib import Path
from threading import Thread
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import TypeVar

from config import (
    ALL_TEAMS_LABEL,
    FOOTBALL_LEAGUES,
    LEAGUE_GROUPS,
    LEAGUE_SELECTION_PROMPT,
)
from log_settings import (
    LogFileSettings,
    SettingsError,
    load_log_settings,
    load_selected_leagues,
    save_application_settings,
)
from football_api import (
    FootballMatch,
    FootballTeam,
    format_league_table,
    format_match_list,
    get_football_teams,
    get_league_badge_bytes,
    get_league_table,
    get_matches,
)
from helpers import FootballDataError, get_espn_image
from logging_service import (
    LogName,
    check_log_file_integrity,
    configure_log_files,
    format_log_file,
    get_integrity_warnings,
    log_application_activity,
    log_application_error,
)
from test_runner import run_all_tests


TaskResult = TypeVar("TaskResult")


class FootballMonitorWindow:
    """Show league and team choices and display their real ESPN match details."""

    def __init__(self, window: tk.Tk) -> None:
        """Create the window and show the league selection prompt."""
        self.window = window
        self.window.title("ESPN Football Monitor")
        self.window.geometry("850x620")
        self.window.minsize(650, 450)

        self.selected_league = tk.StringVar(value=LEAGUE_SELECTION_PROMPT)
        self.selected_team = tk.StringVar(value=ALL_TEAMS_LABEL)
        self.status_message = tk.StringVar(value="Choose a league to get started.")
        self.selected_leagues = load_selected_leagues()
        self.team_ids_by_name: dict[str, str] = {}
        self.teams_by_name: dict[str, FootballTeam] = {}
        self.request_number = 0
        self.log_settings = load_log_settings()
        configure_log_files(self.log_settings)

        self.build_window()
        self.window.protocol("WM_DELETE_WINDOW", self.exit_application)
        log_application_activity("Football Monitor window opened.")
        integrity_warnings = get_integrity_warnings()
        if integrity_warnings:
            self.status_message.set(
                "A log has an integrity or file-permission warning. "
                "Open the cog settings to review it."
            )

    def build_window(self) -> None:
        """Place settings, choices, badges, information tabs, and exit control."""
        main_area = ttk.Frame(self.window, padding=16)
        main_area.pack(fill="both", expand=True)

        top_bar = ttk.Frame(main_area)
        top_bar.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.settings_button = ttk.Button(
            top_bar,
            text="⚙",
            width=3,
            command=self.open_log_settings,
        )
        self.settings_button.pack(side="right")

        ttk.Label(main_area, text="Football league:").grid(
            row=1,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=6,
        )
        self.league_menu = ttk.Combobox(
            main_area,
            textvariable=self.selected_league,
            values=self.selected_leagues,
            state="readonly",
        )
        ttk.Style(self.window).configure(
            "LeaguePrompt.TCombobox",
            foreground="#999999",
        )
        self.league_menu.configure(style="LeaguePrompt.TCombobox")
        self.league_menu.grid(row=1, column=1, sticky="ew", pady=6)
        self.league_badge_label = ttk.Label(main_area)
        self.league_badge_label.grid(
            row=1,
            column=2,
            rowspan=1,
            padx=(18, 0),
            pady=6,
        )
        self.league_menu.bind(
            "<<ComboboxSelected>>",
            self.load_teams_for_selected_league,
        )

        ttk.Label(main_area, text="Team:").grid(
            row=2,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=6,
        )
        self.team_menu = ttk.Combobox(
            main_area,
            textvariable=self.selected_team,
            values=[ALL_TEAMS_LABEL],
            state="disabled",
        )
        self.team_menu.grid(row=2, column=1, sticky="ew", pady=6)
        self.team_badge_label = ttk.Label(main_area)
        self.team_badge_label.grid(
            row=2,
            column=2,
            padx=(18, 0),
            pady=6,
        )
        self.team_menu.bind(
            "<<ComboboxSelected>>",
            self.show_selected_matches,
        )

        self.status_label = ttk.Label(
            main_area,
            textvariable=self.status_message,
            wraplength=780,
        )
        self.status_label.grid(
            row=3,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(0, 8),
        )

        information_tabs = ttk.Notebook(main_area)
        information_tabs.grid(
            row=4,
            column=0,
            columnspan=3,
            sticky="nsew",
        )
        results_area = ttk.Frame(information_tabs)
        table_area = ttk.Frame(information_tabs)
        information_tabs.add(results_area, text="Results and Fixtures")
        information_tabs.add(table_area, text="Table")
        self.results_box = self.make_read_only_text_area(results_area, "word")
        self.table_box = self.make_read_only_text_area(table_area, "none")

        self.exit_button = ttk.Button(
            main_area,
            text="Exit",
            command=self.exit_application,
        )
        self.exit_button.grid(
            row=5,
            column=2,
            sticky="e",
            pady=(10, 0),
        )

        main_area.columnconfigure(2, minsize=120)
        main_area.columnconfigure(1, weight=1)
        main_area.rowconfigure(4, weight=1)
        self.show_results(
            "Choose a league and team. The program will get current information "
            "directly from ESPN."
        )
        self.show_table(
            "Choose a league to see its current table, if ESPN provides one."
        )

    def make_read_only_text_area(
        self,
        parent: ttk.Frame,
        word_wrap: str,
    ) -> tk.Text:
        """Create a scrollable text area that people can read but not edit."""
        text_area = tk.Text(
            parent,
            wrap=word_wrap,
            state="disabled",
            font=("Consolas", 10) if word_wrap == "none" else ("Segoe UI", 10),
        )
        scroll_bar = ttk.Scrollbar(
            parent,
            orient="vertical",
            command=text_area.yview,
        )
        text_area.configure(yscrollcommand=scroll_bar.set)
        text_area.pack(side="left", fill="both", expand=True)
        scroll_bar.pack(side="right", fill="y")
        return text_area

    def load_teams_for_selected_league(
        self,
        event: tk.Event | None = None,
    ) -> None:
        """Get real team choices for the league selected in the first menu."""
        del event
        league_name = self.selected_league.get()
        if league_name == LEAGUE_SELECTION_PROMPT:
            self.team_ids_by_name = {}
            self.teams_by_name = {}
            self.show_badge(None, "league")
            self.show_badge(None, "team")
            self.team_menu.configure(
                values=[ALL_TEAMS_LABEL],
                state="disabled",
            )
            self.status_message.set("Choose a football league to get started.")
            return

        log_application_activity(f"League selected: {league_name}.")
        self.league_menu.configure(style="TCombobox")
        self.show_badge(None, "league")
        self.show_badge(None, "team")
        self.selected_team.set(ALL_TEAMS_LABEL)
        self.team_menu.configure(values=[ALL_TEAMS_LABEL], state="disabled")
        self.status_message.set(f"Getting teams in {league_name} from ESPN...")
        self.show_table(f"Getting the current table for {league_name} from ESPN...")
        self.start_background_task(
            "loading football teams",
            lambda: self.load_league_selection_data(league_name),
            lambda league_data: self.finish_loading_teams(
                league_name,
                league_data[0],
                league_data[1],
                league_data[2],
            ),
        )

    def load_league_selection_data(
        self,
        league_name: str,
    ) -> tuple[list[FootballTeam], bytes | None, str]:
        """Load teams, badges, and table information for the selected league."""
        teams = get_football_teams(league_name)
        try:
            league_badge_bytes = get_league_badge_bytes(league_name)
        except (FootballDataError, OSError, ValueError) as error:
            log_application_error(
                "loading the selected league badge",
                str(error),
                "Check the internet connection. The league and teams can still "
                "be used without a badge.",
                error,
            )
            league_badge_bytes = None
        try:
            table_rows = get_league_table(league_name)
            table_report = format_league_table(league_name, table_rows)
        except (FootballDataError, OSError, ValueError) as error:
            log_application_error(
                "loading the selected league table",
                str(error),
                "Check the internet connection and open the Table tab again "
                "after choosing the league.",
                error,
            )
            table_report = (
                f"Current table: {league_name}\n\n"
                "ESPN's table information could not be loaded. "
                "You can still view the teams and matches."
            )
        return teams, league_badge_bytes, table_report

    def finish_loading_teams(
        self,
        league_name: str,
        teams: list[FootballTeam],
        league_badge_bytes: bytes | None = None,
        table_report: str | None = None,
    ) -> None:
        """Put ESPN's teams in the second menu and allow match searches."""
        if league_name != self.selected_league.get():
            return
        self.team_ids_by_name = {
            team.name: team.team_id
            for team in teams
        }
        self.teams_by_name = {team.name: team for team in teams}
        team_names = [ALL_TEAMS_LABEL, *self.team_ids_by_name]
        self.team_menu.configure(values=team_names, state="readonly")
        self.show_badge(league_badge_bytes, "league")
        if table_report is not None:
            self.show_table(table_report)
        self.status_message.set(
            f"Loaded {len(self.team_ids_by_name)} teams from ESPN. "
            "Choose a team or all teams to load matches."
        )
        log_application_activity(
            f"Loaded {len(self.team_ids_by_name)} teams for {league_name}."
        )

    def show_selected_matches(
        self,
        event: tk.Event | None = None,
    ) -> None:
        """Get the selected team's fixtures or the league's current matches."""
        del event
        league_name = self.selected_league.get()
        team_name = self.selected_team.get() or ALL_TEAMS_LABEL
        team_id = (
            None
            if team_name == ALL_TEAMS_LABEL
            else self.team_ids_by_name.get(team_name)
        )
        if team_name != ALL_TEAMS_LABEL and team_id is None:
            self.show_problem(
                "The selected team is not in the current team list. "
                "Choose the league again and try once more."
            )
            return

        selected_team = self.teams_by_name.get(team_name)
        self.show_badge(None, "team")
        self.status_message.set("Getting real match information from ESPN...")
        self.start_background_task(
            "loading football matches",
            lambda: self.load_match_details(
                league_name,
                team_name,
                team_id,
                selected_team,
            ),
            lambda result: self.finish_loading_matches(
                league_name,
                team_name,
                result,
            ),
        )

    def finish_loading_matches(
        self,
        league_name: str,
        team_name: str,
        result: tuple[list[FootballMatch], str, bytes | None],
    ) -> None:
        """Display the match details and say when ESPN was checked."""
        matches, checked_at, team_badge_bytes = result
        report = format_match_list(
            league_name,
            team_name,
            matches,
            checked_at,
        )
        self.show_results(report)
        if team_name != ALL_TEAMS_LABEL:
            self.show_badge(team_badge_bytes, "team")
        self.status_message.set(f"ESPN information checked at {checked_at}.")
        log_application_activity(
            f"Displayed {len(matches)} matches for {league_name}, {team_name}."
        )

    def load_match_details(
        self,
        league_name: str,
        team_name: str,
        team_id: str | None,
        selected_team: FootballTeam | None,
    ) -> tuple[list[FootballMatch], str, bytes | None]:
        """Load match details and, for one team, its badge image."""
        matches, checked_at = get_matches(league_name, team_id)
        if team_name == ALL_TEAMS_LABEL or selected_team is None:
            return matches, checked_at, None
        if not selected_team.badge_url:
            return matches, checked_at, None
        try:
            badge_bytes = get_espn_image(selected_team.badge_url)
        except (FootballDataError, OSError, ValueError) as error:
            log_application_error(
                "loading the selected team badge",
                str(error),
                "Check the internet connection. The match information can still "
                "be used without the badge.",
                error,
            )
            badge_bytes = None
        return matches, checked_at, badge_bytes

    def show_badge(self, badge_bytes: bytes | None, badge_kind: str) -> None:
        """Show one small ESPN badge or clear its place when there is none."""
        badge_label = (
            self.league_badge_label
            if badge_kind == "league"
            else self.team_badge_label
        )
        badge_image: tk.PhotoImage | None = None
        if badge_bytes:
            badge_image = tk.PhotoImage(
                master=self.window,
                data=base64.b64encode(badge_bytes),
            )
            width_shrink = max(1, (badge_image.width() + 99) // 100)
            height_shrink = max(1, (badge_image.height() + 99) // 100)
            shrink_by = max(width_shrink, height_shrink)
            if shrink_by > 1:
                badge_image = badge_image.subsample(shrink_by, shrink_by)

        if badge_kind == "league":
            self.league_badge_image = badge_image
        else:
            self.team_badge_image = badge_image
        badge_label.configure(image=badge_image or "")

    def exit_application(self) -> None:
        """Close the main window when the user presses Exit."""
        log_application_activity("The user chose to exit Football Monitor.")
        try:
            self.window.destroy()
        except tk.TclError as error:
            log_application_error(
                "closing the Football Monitor window",
                str(error),
                "Close the window again. If the problem continues, restart the app.",
                error,
            )

    def start_background_task(
        self,
        task_description: str,
        task_to_run: Callable[[], TaskResult],
        task_succeeded: Callable[[TaskResult], None],
    ) -> None:
        """Run a web request without freezing the window and show any failure."""
        self.request_number += 1
        this_request_number = self.request_number

        def do_task() -> None:
            """Run one request and safely return its result to the window."""
            try:
                task_result = task_to_run()
            except (FootballDataError, OSError, ValueError) as error:
                problem_message = str(error)
                log_application_error(
                    task_description,
                    str(error),
                    "Check the internet connection and the external log settings, "
                    "then try the action again.",
                    error,
                )
                self.window.after(
                    0,
                    lambda: self.finish_task_with_problem(
                        this_request_number,
                        problem_message,
                        task_description,
                    ),
                )
                return
            except Exception as error:
                problem_message = (
                    "The program ran into an unexpected problem while "
                    f"{task_description}: {type(error).__name__}: {error}"
                )
                log_application_error(
                    task_description,
                    problem_message,
                    "Check the application log for the error details, then try "
                    "the action again.",
                    error,
                )
                self.window.after(
                    0,
                    lambda: self.finish_task_with_problem(
                        this_request_number,
                        problem_message,
                        task_description,
                    ),
                )
                return

            self.window.after(
                0,
                lambda: self.finish_task_if_current(
                    this_request_number,
                    task_succeeded,
                    task_result,
                ),
            )

        try:
            Thread(target=do_task, daemon=True).start()
        except (RuntimeError, OSError) as error:
            log_application_error(
                "starting a background task",
                f"The program could not start {task_description}: {error}",
                "Close other applications using system resources, then try again.",
                error,
            )
            self.show_problem(
                f"The program could not start {task_description}. "
                f"Details: {error}"
            )

    def finish_task_if_current(
        self,
        request_number: int,
        task_succeeded: Callable[[TaskResult], None],
        task_result: TaskResult,
    ) -> None:
        """Ignore an old reply so it cannot overwrite newer league choices."""
        if request_number == self.request_number:
            task_succeeded(task_result)

    def finish_task_with_problem(
        self,
        request_number: int,
        problem_message: str,
        task_description: str,
    ) -> None:
        """Show a failed request only if it still belongs to the current choice."""
        if request_number != self.request_number:
            return
        self.status_message.set("ESPN information could not be loaded.")
        self.show_results(problem_message)
        if task_description == "loading football teams":
            self.show_table(
                f"Current table: {self.selected_league.get()}\n\n"
                "ESPN information could not be loaded. "
                "Please choose the league again later."
            )
        messagebox.showerror(
            "Football information could not be loaded",
            problem_message,
            parent=self.window,
        )

    def show_problem(self, problem_message: str) -> None:
        """Show a clear problem message in the results and status areas."""
        log_application_error(
            "checking the user's football choices",
            problem_message,
            "Choose a league and team from the menus, then try again.",
        )
        self.status_message.set("Please check the football choices and try again.")
        self.show_results(problem_message)
        messagebox.showerror(
            "Football Monitor problem",
            problem_message,
            parent=self.window,
        )

    def show_results(self, readable_text: str) -> None:
        """Replace the words in the results area without making it editable."""
        self.replace_read_only_text(self.results_box, readable_text)

    def show_table(self, readable_text: str) -> None:
        """Replace the words in the Table tab without making it editable."""
        self.replace_read_only_text(self.table_box, readable_text)

    def replace_read_only_text(
        self,
        text_area: tk.Text,
        readable_text: str,
    ) -> None:
        """Change text in a read-only area while keeping it locked afterward."""
        text_area.configure(state="normal")
        text_area.delete("1.0", "end")
        text_area.insert("1.0", readable_text)
        text_area.configure(state="disabled")

    def open_log_settings(self) -> None:
        """Open the cog window for changing paths and viewing the logs."""
        log_application_activity("The user opened log settings.")
        LogSettingsWindow(self)

    def apply_selected_leagues(self, selected_leagues: list[str]) -> None:
        """Update the league menu and clear a league that was switched off."""
        self.selected_leagues = [
            league_name
            for league_name in FOOTBALL_LEAGUES
            if league_name in selected_leagues
        ]
        self.league_menu.configure(
            values=self.selected_leagues,
            state="readonly" if self.selected_leagues else "disabled",
        )
        if self.selected_league.get() in self.selected_leagues:
            return

        self.request_number += 1
        self.selected_league.set(LEAGUE_SELECTION_PROMPT)
        self.selected_team.set(ALL_TEAMS_LABEL)
        self.team_ids_by_name = {}
        self.teams_by_name = {}
        self.team_menu.configure(values=[ALL_TEAMS_LABEL], state="disabled")
        self.league_menu.configure(style="LeaguePrompt.TCombobox")
        self.show_badge(None, "league")
        self.show_badge(None, "team")
        if self.selected_leagues:
            self.status_message.set("Choose a league to get started.")
            self.show_results("Choose a league to see its results and fixtures.")
            self.show_table("Choose a league to see its current table.")
        else:
            self.status_message.set(
                "No leagues are selected. Open the cog to choose leagues."
            )
            self.show_results(
                "No leagues are selected. Open the cog settings and choose "
                "at least one league."
            )
            self.show_table(
                "No leagues are selected. Open the cog settings and choose "
                "at least one league."
            )


class LogSettingsWindow:
    """Let the user choose leagues, save log paths, run tests, and view logs."""

    def __init__(self, monitor: FootballMonitorWindow) -> None:
        """Create one separate settings window attached to the main app."""
        self.monitor = monitor
        self.window = tk.Toplevel(monitor.window)
        self.window.title("Football Monitor Settings and Logs")
        self.window.geometry("800x720")
        self.window.minsize(680, 560)
        self.window.transient(monitor.window)
        self.path_fields: dict[str, tk.StringVar] = {}
        self.league_checkbox_values: dict[str, tk.BooleanVar] = {}
        self.build_settings_window()

    def build_settings_window(self) -> None:
        """Show league checkboxes, log paths, and read-only log buttons."""
        settings_area = ttk.Frame(self.window, padding=16)
        settings_area.pack(fill="both", expand=True)

        log_rows = [
            (
                "API communications log",
                "api_communications_log",
                self.monitor.log_settings.api_communications_log,
            ),
            (
                "Application log",
                "application_log",
                self.monitor.log_settings.application_log,
            ),
            (
                "Testing log",
                "testing_log",
                self.monitor.log_settings.testing_log,
            ),
        ]
        for row_number, (label, setting_name, current_path) in enumerate(log_rows):
            ttk.Label(settings_area, text=label).grid(
                row=row_number,
                column=0,
                sticky="w",
                padx=(0, 8),
                pady=7,
            )
            file_path = tk.StringVar(value=current_path)
            self.path_fields[setting_name] = file_path
            ttk.Entry(
                settings_area,
                textvariable=file_path,
                state="readonly",
            ).grid(row=row_number, column=1, sticky="ew", pady=7)
            ttk.Button(
                settings_area,
                text="Choose file",
                command=lambda name=setting_name: self.choose_log_file(name),
            ).grid(row=row_number, column=2, padx=5, pady=7)
            ttk.Button(
                settings_area,
                text="Open log",
                command=lambda title=label, name=setting_name: self.open_log(
                    title,
                    name,
                ),
            ).grid(row=row_number, column=3, pady=7)

        ttk.Label(
            settings_area,
            text="Leagues shown in the main window",
        ).grid(
            row=3,
            column=0,
            columnspan=4,
            sticky="w",
            pady=(12, 4),
        )
        league_list_area = ttk.Frame(settings_area, height=260)
        league_list_area.grid(
            row=4,
            column=0,
            columnspan=4,
            sticky="nsew",
        )
        league_list_area.grid_propagate(False)
        league_canvas = tk.Canvas(league_list_area, highlightthickness=0)
        league_scroll_bar = ttk.Scrollbar(
            league_list_area,
            orient="vertical",
            command=league_canvas.yview,
        )
        league_contents = ttk.Frame(league_canvas)

        def update_league_scroll_region(event: tk.Event) -> None:
            """Keep all league checkboxes reachable with the scroll bar."""
            del event
            league_canvas.configure(scrollregion=league_canvas.bbox("all"))

        league_contents.bind("<Configure>", update_league_scroll_region)
        league_window = league_canvas.create_window(
            (0, 0),
            window=league_contents,
            anchor="nw",
        )
        league_canvas.configure(yscrollcommand=league_scroll_bar.set)
        league_canvas.bind(
            "<Configure>",
            lambda event: league_canvas.itemconfigure(
                league_window,
                width=event.width,
            ),
        )
        league_canvas.pack(side="left", fill="both", expand=True)
        league_scroll_bar.pack(side="right", fill="y")
        self.build_league_checkboxes(league_contents)

        action_buttons = ttk.Frame(settings_area)
        action_buttons.grid(
            row=5,
            column=0,
            columnspan=4,
            sticky="e",
            pady=(12, 0),
        )
        ttk.Button(
            action_buttons,
            text="Run tests and save results",
            command=self.run_tests,
        ).pack(side="left", padx=5)
        ttk.Button(
            action_buttons,
            text="Save settings",
            command=self.save_settings,
        ).pack(side="left", padx=5)
        settings_area.columnconfigure(1, weight=1)
        settings_area.rowconfigure(4, weight=1)

        integrity_warnings = get_integrity_warnings()
        if integrity_warnings:
            ttk.Label(
                settings_area,
                text="\n".join(integrity_warnings),
                foreground="#b00020",
                wraplength=700,
            ).grid(row=6, column=0, columnspan=4, sticky="w", pady=(12, 0))

    def build_league_checkboxes(self, parent: ttk.Frame) -> None:
        """Show a check box for every ESPN league, grouped by location."""
        selected_league_names = set(self.monitor.selected_leagues)
        for group_number, (group_name, league_names) in enumerate(
            LEAGUE_GROUPS.items()
        ):
            group_area = ttk.LabelFrame(parent, text=group_name, padding=8)
            group_area.grid(
                row=group_number // 2,
                column=group_number % 2,
                sticky="nsew",
                padx=5,
                pady=5,
            )
            for row_number, league_name in enumerate(league_names):
                selected = tk.BooleanVar(
                    master=self.window,
                    value=league_name in selected_league_names,
                )
                self.league_checkbox_values[league_name] = selected
                ttk.Checkbutton(
                    group_area,
                    text=league_name,
                    variable=selected,
                ).grid(row=row_number, column=0, sticky="w", pady=2)
            parent.columnconfigure(group_number % 2, weight=1)

    def choose_log_file(self, setting_name: str) -> None:
        """Let the user choose where one log file will be stored."""
        current_path = self.path_fields[setting_name].get()
        selected_path = filedialog.asksaveasfilename(
            parent=self.window,
            title="Choose a log file outside the program folder",
            initialdir=str(Path(current_path).parent),
            initialfile=Path(current_path).name,
            defaultextension=".txt",
            filetypes=[("Text log files", "*.txt"), ("All files", "*.*")],
        )
        if selected_path:
            self.path_fields[setting_name].set(selected_path)

    def save_settings(self) -> None:
        """Save log paths and league choices, then update the main window."""
        new_settings = LogFileSettings(
            api_communications_log=self.path_fields[
                "api_communications_log"
            ].get(),
            application_log=self.path_fields["application_log"].get(),
            testing_log=self.path_fields["testing_log"].get(),
        )
        selected_leagues = [
            league_name
            for league_name in FOOTBALL_LEAGUES
            if self.league_checkbox_values[league_name].get()
        ]
        try:
            save_application_settings(new_settings, selected_leagues)
            configure_log_files(new_settings)
        except (SettingsError, OSError) as error:
            log_application_error(
                "saving log settings",
                str(error),
                "Choose three different file paths outside the program folder "
                "and check that the folders are writable.",
                error,
            )
            messagebox.showerror(
                "Log settings could not be saved",
                str(error),
                parent=self.window,
            )
            return

        self.monitor.log_settings = new_settings
        self.monitor.apply_selected_leagues(selected_leagues)
        log_application_activity("The user saved new log file paths.")
        messagebox.showinfo(
            "Log settings saved",
            "Your log file locations and league choices have been saved.",
            parent=self.window,
        )
        self.window.destroy()

    def open_log(self, log_title: str, setting_name: str) -> None:
        """Check a log's checksum and open its contents in a locked viewer."""
        log_path = self.path_fields[setting_name].get()
        log_name_by_setting: dict[str, LogName] = {
            "api_communications_log": "api_communications_log",
            "application_log": "application_log",
            "testing_log": "testing_log",
        }
        try:
            log_is_valid = check_log_file_integrity(
                log_name_by_setting[setting_name],
                log_path,
            )
            displayed_text = format_log_file(log_path, log_is_valid)
        except (OSError, UnicodeError) as error:
            log_application_error(
                f"opening the {log_title.lower()}",
                str(error),
                "Check that the selected file exists and this account can read it.",
                error,
            )
            messagebox.showerror(
                "Log could not be opened",
                "The selected log could not be read. Check the file path and "
                f"permissions.\n\nDetails: {error}",
                parent=self.window,
            )
            return
        show_read_only_log(self.window, log_title, displayed_text)
        log_application_activity(f"The user opened the {log_title.lower()}.")

    def run_tests(self) -> None:
        """Run the unit tests and show the same full output saved to the log."""
        try:
            tests_passed, full_results = run_all_tests()
        except (ImportError, OSError, RuntimeError, ValueError) as error:
            log_application_error(
                "running the project tests",
                str(error),
                "Check the project test folder and testing log path, then try again.",
                error,
            )
            messagebox.showerror(
                "Tests could not be run",
                "The tests could not be completed. Check the application log "
                f"for details.\n\nDetails: {error}",
                parent=self.window,
            )
            return

        result_title = "All tests passed" if tests_passed else "Some tests failed"
        show_read_only_log(self.window, result_title, full_results)
        log_application_activity(f"Tests were run. Passed: {tests_passed}.")


def show_read_only_log(
    parent_window: tk.Misc,
    title: str,
    log_text: str,
) -> None:
    """Display log contents in a window where typing and editing are disabled."""
    viewer = tk.Toplevel(parent_window)
    viewer.title(title)
    viewer.geometry("900x560")
    log_box = tk.Text(
        viewer,
        wrap="none",
        state="normal",
        font=("Consolas", 9),
    )
    vertical_scroll_bar = ttk.Scrollbar(
        viewer,
        orient="vertical",
        command=log_box.yview,
    )
    horizontal_scroll_bar = ttk.Scrollbar(
        viewer,
        orient="horizontal",
        command=log_box.xview,
    )
    log_box.configure(
        yscrollcommand=vertical_scroll_bar.set,
        xscrollcommand=horizontal_scroll_bar.set,
    )
    log_box.grid(row=0, column=0, sticky="nsew")
    vertical_scroll_bar.grid(row=0, column=1, sticky="ns")
    horizontal_scroll_bar.grid(row=1, column=0, sticky="ew")
    viewer.rowconfigure(0, weight=1)
    viewer.columnconfigure(0, weight=1)
    log_box.insert("1.0", log_text)
    log_box.configure(state="disabled")


def launch_gui() -> None:
    """Open the Football Monitor window and keep it running for the user."""
    try:
        window = tk.Tk()
        FootballMonitorWindow(window)
        window.mainloop()
    except (SettingsError, OSError) as error:
        messagebox.showerror(
            "Football Monitor could not prepare its logs",
            "The program could not read its external log settings or prepare "
            "the log files. Check the settings file and folder permissions, "
            f"then try again.\n\nDetails: {error}",
        )
    except tk.TclError as error:
        messagebox.showerror(
            "Football Monitor could not start",
            "The program could not open its window. Check that your desktop "
            f"is available, then try again.\n\nDetails: {error}",
        )
