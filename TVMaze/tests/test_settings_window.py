"""Check that the Settings window opens logs without allowing changes."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from config import AppSettings
from helpers import save_log_checksum
from settings_window import SettingsWindow


class SettingsLogViewerTests(unittest.TestCase):
    """Check that log buttons show the chosen file in the safe viewer."""

    def make_settings_window(self, log_file_path: Path) -> SettingsWindow:
        """Make a settings window shell that does not create a real window."""
        settings_window = SettingsWindow.__new__(SettingsWindow)
        settings_window.setting_boxes = {
            "api_activity_log_path": Mock(get=Mock(return_value=str(log_file_path)))
        }
        settings_window.window = Mock()
        return settings_window

    def test_log_button_uses_the_read_only_viewer(self) -> None:
        """A log button should read the file and show it in the protected viewer."""
        with tempfile.TemporaryDirectory() as folder:
            log_file_path = Path(folder) / "API_activity_logging.log"
            log_file_path.write_text("Saved API note.", encoding="utf-8")
            save_log_checksum(
                log_file_path,
                Path(f"{log_file_path}.sha256"),
            )
            settings_window = self.make_settings_window(log_file_path)

            with patch(
                "settings_window.show_read_only_text_window"
            ) as show_read_only_window:
                settings_window.view_log_file(
                    "api_activity_log_path",
                    "API issue log",
                )

        show_read_only_window.assert_called_once_with(
            settings_window.window,
            "Read API issue log",
            "Saved API note.",
            False,
        )

    def test_missing_log_file_shows_a_clear_message(self) -> None:
        """A missing log should tell the person why the viewer did not open."""
        with tempfile.TemporaryDirectory() as folder:
            missing_file = Path(folder) / "not-made-yet.log"
            settings_window = self.make_settings_window(missing_file)

            with (
                patch("settings_window.show_read_only_text_window") as show_viewer,
                patch("settings_window.messagebox.showerror") as show_error,
                patch("settings_window.log_application_error") as log_problem,
            ):
                settings_window.view_log_file(
                    "api_activity_log_path",
                    "API issue log",
                )

        show_viewer.assert_not_called()
        show_error.assert_called_once()
        self.assertIn("could not read", show_error.call_args.args[1])
        log_problem.assert_called_once()

    def test_unreadable_log_file_shows_a_clear_message(self) -> None:
        """Text that is not readable should not crash the Settings window."""
        with tempfile.TemporaryDirectory() as folder:
            log_file_path = Path(folder) / "unreadable.log"
            log_file_path.write_bytes(b"\xff")
            settings_window = self.make_settings_window(log_file_path)

            with (
                patch("settings_window.show_read_only_text_window") as show_viewer,
                patch("settings_window.messagebox.showerror") as show_error,
                patch("settings_window.log_application_error") as log_problem,
            ):
                settings_window.view_log_file(
                    "api_activity_log_path",
                    "API issue log",
                )

        show_viewer.assert_not_called()
        show_error.assert_called_once()
        self.assertIn("could not read", show_error.call_args.args[1])
        log_problem.assert_called_once()

    def test_changed_log_is_shown_with_an_outside_edit_warning(self) -> None:
        """Settings should detect a changed log and tell the read-only viewer."""
        with tempfile.TemporaryDirectory() as folder:
            log_file_path = Path(folder) / "API_activity_logging.log"
            log_file_path.write_text("Changed log note.", encoding="utf-8")
            settings_window = self.make_settings_window(log_file_path)

            with (
                patch(
                    "settings_window.log_file_matches_saved_checksum",
                    return_value=False,
                ),
                patch(
                    "settings_window.show_read_only_text_window"
                ) as show_read_only_window,
                patch("settings_window.log_application_issue") as log_issue,
            ):
                settings_window.view_log_file(
                    "api_activity_log_path",
                    "API issue log",
                )

        show_read_only_window.assert_called_once_with(
            settings_window.window,
            "Read API issue log",
            "Changed log note.",
            True,
        )
        log_issue.assert_called_once()
        self.assertIn("changed outside", log_issue.call_args.args[0])

    def test_failed_new_log_locations_restore_the_previous_settings(self) -> None:
        """A log setup failure should restore the original active log locations."""
        settings_window = SettingsWindow.__new__(SettingsWindow)
        previous_settings = AppSettings()
        new_settings = AppSettings(window_title="Another Finder")
        settings_window.current_settings = previous_settings
        settings_window.window = Mock()
        settings_window.make_settings_from_form = Mock(return_value=new_settings)
        settings_window.settings_saved = Mock(
            side_effect=[OSError("The new log folder is not available."), None]
        )

        with (
            patch("settings_window.check_settings"),
            patch("settings_window.save_settings") as save_chosen_settings,
            patch("settings_window.log_application_error") as log_problem,
            patch("settings_window.messagebox.showerror") as show_error,
        ):
            settings_window.save()

        self.assertEqual(
            settings_window.settings_saved.call_args_list,
            [unittest.mock.call(new_settings), unittest.mock.call(previous_settings)],
        )
        save_chosen_settings.assert_not_called()
        log_problem.assert_called_once()
        show_error.assert_called_once()
        self.assertIn("previous log settings have been restored", show_error.call_args.args[1])
        settings_window.window.destroy.assert_not_called()


if __name__ == "__main__":
    unittest.main()
