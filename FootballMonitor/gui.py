"""Build the window where people choose a football league and see ESPN data."""

from collections.abc import Callable
from threading import Thread
import tkinter as tk
from tkinter import messagebox, ttk
from typing import TypeVar

from config import ALL_TEAMS_LABEL, FOOTBALL_LEAGUES
from football_api import (
    FootballMatch,
    FootballTeam,
    format_match_list,
    get_football_teams,
    get_matches,
)
from helpers import FootballDataError


TaskResult = TypeVar("TaskResult")


class FootballMonitorWindow:
    """Show league and team choices and display their real ESPN match details."""

    def __init__(self, window: tk.Tk) -> None:
        """Create the window and load the first league's team list."""
        self.window = window
        self.window.title("ESPN Football Monitor")
        self.window.geometry("850x620")
        self.window.minsize(650, 450)

        self.selected_league = tk.StringVar(
            value=next(iter(FOOTBALL_LEAGUES))
        )
        self.selected_team = tk.StringVar(value=ALL_TEAMS_LABEL)
        self.status_message = tk.StringVar(value="Choose a league to get started.")
        self.team_ids_by_name: dict[str, str] = {}
        self.request_number = 0

        self.build_window()
        self.load_teams_for_selected_league()

    def build_window(self) -> None:
        """Place the league menu, team menu, refresh button, and results."""
        main_area = ttk.Frame(self.window, padding=16)
        main_area.pack(fill="both", expand=True)

        ttk.Label(main_area, text="Football league:").grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=6,
        )
        self.league_menu = ttk.Combobox(
            main_area,
            textvariable=self.selected_league,
            values=list(FOOTBALL_LEAGUES),
            state="readonly",
        )
        self.league_menu.grid(row=0, column=1, sticky="ew", pady=6)
        self.league_menu.bind(
            "<<ComboboxSelected>>",
            self.load_teams_for_selected_league,
        )

        ttk.Label(main_area, text="Team:").grid(
            row=1,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=6,
        )
        self.team_menu = ttk.Combobox(
            main_area,
            textvariable=self.selected_team,
            values=[ALL_TEAMS_LABEL],
            state="readonly",
        )
        self.team_menu.grid(row=1, column=1, sticky="ew", pady=6)
        self.team_menu.bind(
            "<<ComboboxSelected>>",
            self.show_selected_matches,
        )

        self.refresh_button = ttk.Button(
            main_area,
            text="Refresh football information",
            command=self.show_selected_matches,
        )
        self.refresh_button.grid(row=2, column=1, sticky="e", pady=(6, 12))

        self.status_label = ttk.Label(
            main_area,
            textvariable=self.status_message,
            wraplength=780,
        )
        self.status_label.grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(0, 8),
        )

        results_area = ttk.Frame(main_area)
        results_area.grid(
            row=4,
            column=0,
            columnspan=2,
            sticky="nsew",
        )
        self.results_box = tk.Text(
            results_area,
            wrap="word",
            state="disabled",
            font=("Segoe UI", 10),
        )
        results_scroll_bar = ttk.Scrollbar(
            results_area,
            orient="vertical",
            command=self.results_box.yview,
        )
        self.results_box.configure(yscrollcommand=results_scroll_bar.set)
        self.results_box.pack(side="left", fill="both", expand=True)
        results_scroll_bar.pack(side="right", fill="y")

        main_area.columnconfigure(1, weight=1)
        main_area.rowconfigure(4, weight=1)
        self.show_results(
            "Choose a league and team. The program will get current information "
            "directly from ESPN."
        )

    def load_teams_for_selected_league(
        self,
        event: tk.Event | None = None,
    ) -> None:
        """Get real team choices for the league selected in the first menu."""
        del event
        league_name = self.selected_league.get()
        self.selected_team.set(ALL_TEAMS_LABEL)
        self.team_menu.configure(values=[ALL_TEAMS_LABEL], state="disabled")
        self.refresh_button.configure(state="disabled")
        self.status_message.set(f"Getting teams in {league_name} from ESPN...")
        self.start_background_task(
            "loading football teams",
            lambda: get_football_teams(league_name),
            lambda teams: self.finish_loading_teams(league_name, teams),
        )

    def finish_loading_teams(
        self,
        league_name: str,
        teams: list[FootballTeam],
    ) -> None:
        """Put ESPN's teams in the second menu and allow match searches."""
        if league_name != self.selected_league.get():
            return
        self.team_ids_by_name = {
            team.name: team.team_id
            for team in teams
        }
        team_names = [ALL_TEAMS_LABEL, *self.team_ids_by_name]
        self.team_menu.configure(values=team_names, state="readonly")
        self.refresh_button.configure(state="normal")
        self.status_message.set(
            f"Loaded {len(self.team_ids_by_name)} teams from ESPN. "
            "Choose a team or all teams, then refresh."
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

        self.refresh_button.configure(state="disabled")
        self.status_message.set("Getting real match information from ESPN...")
        self.start_background_task(
            "loading football matches",
            lambda: get_matches(league_name, team_id),
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
        result: tuple[list[FootballMatch], str],
    ) -> None:
        """Display the match details and say when ESPN was checked."""
        matches, checked_at = result
        report = format_match_list(
            league_name,
            team_name,
            matches,
            checked_at,
        )
        self.show_results(report)
        self.status_message.set(f"ESPN information checked at {checked_at}.")
        self.refresh_button.configure(state="normal")

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
                self.window.after(
                    0,
                    lambda: self.finish_task_with_problem(
                        this_request_number,
                        problem_message,
                    ),
                )
                return
            except Exception as error:
                problem_message = (
                    "The program ran into an unexpected problem while "
                    f"{task_description}: {type(error).__name__}: {error}"
                )
                self.window.after(
                    0,
                    lambda: self.finish_task_with_problem(
                        this_request_number,
                        problem_message,
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
            self.refresh_button.configure(state="normal")
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
    ) -> None:
        """Show a failed request only if it still belongs to the current choice."""
        if request_number != self.request_number:
            return
        self.refresh_button.configure(state="normal")
        self.status_message.set("ESPN information could not be loaded.")
        self.show_results(problem_message)
        messagebox.showerror(
            "Football information could not be loaded",
            problem_message,
            parent=self.window,
        )

    def show_problem(self, problem_message: str) -> None:
        """Show a clear problem message in the results and status areas."""
        self.status_message.set("Please check the football choices and try again.")
        self.show_results(problem_message)
        messagebox.showerror(
            "Football Monitor problem",
            problem_message,
            parent=self.window,
        )

    def show_results(self, readable_text: str) -> None:
        """Replace the words in the results area without making it editable."""
        self.results_box.configure(state="normal")
        self.results_box.delete("1.0", "end")
        self.results_box.insert("1.0", readable_text)
        self.results_box.configure(state="disabled")


def launch_gui() -> None:
    """Open the Football Monitor window and keep it running for the user."""
    try:
        window = tk.Tk()
        FootballMonitorWindow(window)
        window.mainloop()
    except tk.TclError as error:
        messagebox.showerror(
            "Football Monitor could not start",
            "The program could not open its window. Check that your desktop "
            f"is available, then try again.\n\nDetails: {error}",
        )
