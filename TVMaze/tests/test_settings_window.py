"""Check that the Settings window opens logs without allowing changes."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

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
            ):
                settings_window.view_log_file(
                    "api_activity_log_path",
                    "API issue log",
                )

        show_viewer.assert_not_called()
        show_error.assert_called_once()
        self.assertIn("could not be opened", show_error.call_args.args[1])

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


if __name__ == "__main__":
    unittest.main()
