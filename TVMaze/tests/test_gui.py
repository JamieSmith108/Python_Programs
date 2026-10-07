"""Check how the main window handles program choices without opening a window."""

import unittest
from unittest.mock import Mock

from gui import ProgramFinderWindow
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


if __name__ == "__main__":
    unittest.main()
