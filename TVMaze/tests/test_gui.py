"""Check how the main window handles program choices without opening a window."""

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from config import AppSettings
from gui import ProgramFinderWindow
from gui import start_program
from tvmaze_api import TVMazeError
from tvmaze_api import ProgramChoice, ProgramDetails


class ProgramChoiceWindowTests(unittest.TestCase):
    """Check that the selected program is shown and the picker closes."""

    def make_program_choice(self, program_name: str) -> ProgramChoice:
        """Make a small program choice that can be used in a window test."""
        return ProgramChoice(
            program=ProgramDetails(fields={"name": program_name}),
            years_ran="2000 to 2005",
        )

    def test_one_program_is_shown_without_opening_a_choice_popup(self) -> None:
        """A single match should go straight to its full program details."""
        window = ProgramFinderWindow.__new__(ProgramFinderWindow)
        program_choice = self.make_program_choice("One Show")
        window.finish_with_program = Mock()
        window.show_program_choice_popup = Mock()

        window.finish_with_choices([program_choice])

        window.finish_with_program.assert_called_once_with(program_choice.program)
        window.show_program_choice_popup.assert_not_called()

    def test_duplicate_programs_open_the_choice_popup(self) -> None:
        """More than one matching program should be offered for a choice."""
        window = ProgramFinderWindow.__new__(ProgramFinderWindow)
        program_choices = [
            self.make_program_choice("Shared Show"),
            self.make_program_choice("Shared Show"),
        ]
        window.finish_with_program = Mock()
        window.show_program_choice_popup = Mock()

        window.finish_with_choices(program_choices)

        window.show_program_choice_popup.assert_called_once_with(program_choices)
        window.finish_with_program.assert_not_called()

    def test_clicking_a_choice_shows_its_details_and_closes_the_popup(self) -> None:
        """Clicking a picture should show that show's result in the main window."""
        window = ProgramFinderWindow.__new__(ProgramFinderWindow)
        program_choice = self.make_program_choice("Chosen Show")
        popup = Mock()
        window.choice_window = popup
        window.choice_images = [Mock()]
        window.finish_with_program = Mock()

        window.choose_program(program_choice, popup)

        popup.destroy.assert_called_once_with()
        self.assertIsNone(window.choice_window)
        self.assertEqual(window.choice_images, [])
        window.finish_with_program.assert_called_once_with(program_choice.program)

    def test_search_problem_is_logged_and_shown_without_closing_the_window(self) -> None:
        """A failed search should be explained and logged so another search works."""
        window = ProgramFinderWindow.__new__(ProgramFinderWindow)
        window.settings = Mock()
        window.window = Mock()
        window.finish_with_message = Mock()
        search_problem = TVMazeError("Could not connect to TVMaze.")

        with (
            patch("gui.find_program_choices", side_effect=search_problem),
            patch("gui.log_application_error") as log_problem,
        ):
            window.find_program("Example Show")
            show_error_callback = window.window.after.call_args.args[1]
            show_error_callback()

        log_problem.assert_called_once_with(
            "searching for a TV program",
            search_problem,
        )
        window.finish_with_message.assert_called_once_with(
            "Could not connect to TVMaze."
        )

    def test_application_log_start_problem_has_a_clear_message(self) -> None:
        """A missing application log should be explained before the window closes."""
        main_window = Mock()

        with (
            patch("gui.tk.Tk", return_value=main_window),
            patch("gui.load_settings", return_value=AppSettings()),
            patch(
                "gui.start_application_logging",
                side_effect=OSError("The folder cannot be opened."),
            ),
            patch("gui.messagebox.showerror") as show_error,
        ):
            start_program()

        main_window.destroy.assert_called_once_with()
        show_error.assert_called_once()
        self.assertIn(
            "cannot save a record of this problem",
            show_error.call_args.args[1],
        )

    def test_missing_picture_support_is_logged_without_stopping_show_details(self) -> None:
        """A missing picture package should be explained without losing details."""
        window = ProgramFinderWindow.__new__(ProgramFinderWindow)
        window.poster_label = Mock()
        window.poster_image = None

        with (
            patch(
                "gui.make_photo_image",
                side_effect=ImportError("Picture support is missing."),
            ),
            patch("gui.log_application_error") as log_problem,
        ):
            window.show_poster(b"picture")

        window.poster_label.configure.assert_called_once_with(
            image="",
            text="The show image could not be displayed.",
        )
        self.assertIsNone(window.poster_image)
        log_problem.assert_called_once()


if __name__ == "__main__":
    unittest.main()
