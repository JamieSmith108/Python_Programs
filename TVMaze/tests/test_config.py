"""Check that program settings can be saved and loaded safely."""

import tempfile
import unittest
from pathlib import Path

from config import AppSettings, SettingsError, load_settings, save_settings


class SettingsTests(unittest.TestCase):
    """Check how the program remembers editable settings."""

    def test_load_settings_uses_defaults_when_file_is_missing(self) -> None:
        """A first run should start with the built-in settings."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            settings_path = Path(temporary_folder) / "settings.json"

            settings = load_settings(settings_path)

        self.assertEqual(settings, AppSettings())

    def test_save_and_load_settings_remembers_changes(self) -> None:
        """Saved settings should be available after loading them again."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            settings_path = Path(temporary_folder) / "settings.json"
            chosen_settings = AppSettings(window_title="My TV Finder", window_width=800)

            save_settings(chosen_settings, settings_path)
            loaded_settings = load_settings(settings_path)

        self.assertEqual(loaded_settings, chosen_settings)

    def test_load_settings_reports_invalid_saved_values(self) -> None:
        """Bad saved values should be reported instead of silently ignored."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            settings_path = Path(temporary_folder) / "settings.json"
            settings_path.write_text(
                '{"request_timeout_seconds": 0}',
                encoding="utf-8",
            )

            with self.assertRaises(SettingsError):
                load_settings(settings_path)

    def test_save_settings_rejects_window_smaller_than_minimum(self) -> None:
        """A window cannot be smaller than the minimum size it must obey."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            settings_path = Path(temporary_folder) / "settings.json"
            chosen_settings = AppSettings(
                window_width=500,
                minimum_window_width=520,
            )

            with self.assertRaises(SettingsError):
                save_settings(chosen_settings, settings_path)

    def test_save_and_load_settings_remembers_selected_fields(self) -> None:
        """Chosen TVMaze fields should stay selected after restarting."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            settings_path = Path(temporary_folder) / "settings.json"
            chosen_settings = AppSettings(
                selected_show_fields=("name", "image", "_links")
            )

            save_settings(chosen_settings, settings_path)
            loaded_settings = load_settings(settings_path)

        self.assertEqual(loaded_settings.selected_show_fields, ("name", "image", "_links"))

    def test_save_settings_requires_a_known_selected_field(self) -> None:
        """Only fields offered in Settings may be selected."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            settings_path = Path(temporary_folder) / "settings.json"
            chosen_settings = AppSettings(selected_show_fields=("madeUpField",))

            with self.assertRaises(SettingsError):
                save_settings(chosen_settings, settings_path)

    def test_save_settings_requires_at_least_one_selected_field(self) -> None:
        """The results must show at least one field."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            settings_path = Path(temporary_folder) / "settings.json"
            chosen_settings = AppSettings(selected_show_fields=())

            with self.assertRaises(SettingsError):
                save_settings(chosen_settings, settings_path)


if __name__ == "__main__":
    unittest.main()
