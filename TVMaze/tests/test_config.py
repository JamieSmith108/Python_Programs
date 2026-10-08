"""Check that program settings can be saved and loaded safely."""

import json
import tempfile
import unittest
from pathlib import Path

from config import (
    DEFAULT_API_ACTIVITY_LOG_FILE,
    DEFAULT_APPLICATION_LOG_FILE,
    PROGRAM_FOLDER,
    AppSettings,
    SettingsError,
    load_settings,
    save_settings,
)


class SettingsTests(unittest.TestCase):
    """Check how the program remembers editable settings."""

    def test_load_settings_uses_defaults_when_file_is_missing(self) -> None:
        """A first run should start with the built-in settings."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            settings_path = Path(temporary_folder) / "settings.json"

            settings = load_settings(settings_path)

        self.assertEqual(settings, AppSettings())

    def test_default_api_log_is_outside_the_program_folder(self) -> None:
        """The default API issue log should stay outside the program files."""
        self.assertFalse(
            DEFAULT_API_ACTIVITY_LOG_FILE.resolve().is_relative_to(PROGRAM_FOLDER)
        )

    def test_default_application_log_is_outside_the_program_folder(self) -> None:
        """The default application log should stay outside the program files."""
        self.assertFalse(
            DEFAULT_APPLICATION_LOG_FILE.resolve().is_relative_to(PROGRAM_FOLDER)
        )

    def test_saved_settings_remember_the_api_log_location(self) -> None:
        """The chosen API troubleshooting log path should be remembered."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            settings_path = Path(temporary_folder) / "settings.json"
            log_path = Path(temporary_folder) / "logs" / "API_activity_logging.log"
            chosen_settings = AppSettings(api_activity_log_path=str(log_path))

            save_settings(chosen_settings, settings_path)
            loaded_settings = load_settings(settings_path)

        self.assertEqual(loaded_settings.api_activity_log_path, str(log_path))

    def test_settings_accept_only_the_official_tvmaze_search_address(self) -> None:
        """A safe TVMaze search address should be allowed in the settings."""
        settings = AppSettings(
            tvmaze_api_url="https://api.tvmaze.com/singlesearch/shows"
        )

        save_settings(settings, Path(tempfile.gettempdir()) / "settings.json")

    def test_settings_reject_unapproved_web_addresses(self) -> None:
        """Settings must reject insecure, look-alike, and unrelated websites."""
        unsafe_addresses = (
            "http://api.tvmaze.com/singlesearch/shows",
            "https://api.tvmaze.com.evil.example/singlesearch/shows",
            "https://evil.example/api.tvmaze.com/singlesearch/shows",
            "https://api.tvmaze.com@evil.example/singlesearch/shows",
            "https://api.tvmaze.com:8443/singlesearch/shows",
            "https://api.tvmaze.com/shows",
            "https://api.tvmaze.com/singlesearch/shows?other=address",
            "https://api.tvmaze.com/singlesearch/shows#other-place",
        )

        for unsafe_address in unsafe_addresses:
            with self.subTest(address=unsafe_address):
                settings = AppSettings(tvmaze_api_url=unsafe_address)

                with self.assertRaisesRegex(SettingsError, "official secure TVMaze"):
                    save_settings(
                        settings,
                        Path(tempfile.gettempdir()) / "settings.json",
                    )

    def test_settings_reject_an_unreasonable_request_wait_limit(self) -> None:
        """A saved setting cannot make the app wait for an unlimited time."""
        settings = AppSettings(request_timeout_seconds=121)

        with self.assertRaisesRegex(SettingsError, "cannot be longer"):
            save_settings(settings, Path(tempfile.gettempdir()) / "settings.json")

    def test_settings_accept_the_longest_allowed_request_wait_limit(self) -> None:
        """The longest safe wait limit can be saved."""
        settings = AppSettings(request_timeout_seconds=120)

        save_settings(settings, Path(tempfile.gettempdir()) / "settings.json")

    def test_saved_api_log_path_must_be_full_path(self) -> None:
        """The API log location must be a full file path."""
        settings = AppSettings(api_activity_log_path="API_activity_logging.log")

        with self.assertRaises(SettingsError):
            save_settings(settings, Path(tempfile.gettempdir()) / "settings.json")

    def test_saved_api_log_must_be_outside_program_folder(self) -> None:
        """The API log cannot be placed beside the program source files."""
        settings = AppSettings(
            api_activity_log_path=str(PROGRAM_FOLDER / "API_activity_logging.log")
        )

        with self.assertRaises(SettingsError):
            save_settings(settings, Path(tempfile.gettempdir()) / "settings.json")

    def test_saved_application_log_path_is_remembered(self) -> None:
        """The chosen application log location should be saved and loaded."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            settings_path = Path(temporary_folder) / "settings.json"
            log_path = Path(temporary_folder) / "application_log"
            chosen_settings = AppSettings(application_log_path=str(log_path))

            save_settings(chosen_settings, settings_path)
            loaded_settings = load_settings(settings_path)

        self.assertEqual(loaded_settings.application_log_path, str(log_path))

    def test_saved_application_log_path_must_be_full_path(self) -> None:
        """The application log location must be a full file path."""
        settings = AppSettings(application_log_path="application_log")

        with self.assertRaises(SettingsError):
            save_settings(settings, Path(tempfile.gettempdir()) / "settings.json")

    def test_saved_application_log_must_be_outside_program_folder(self) -> None:
        """The application log cannot be placed with the program files."""
        settings = AppSettings(
            application_log_path=str(PROGRAM_FOLDER / "application_log")
        )

        with self.assertRaises(SettingsError):
            save_settings(settings, Path(tempfile.gettempdir()) / "settings.json")

    def test_api_and_application_logs_must_use_different_files(self) -> None:
        """API and application notes must not be mixed into one file."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            same_log_file = Path(temporary_folder) / "all_logs"
            settings = AppSettings(
                api_activity_log_path=str(same_log_file),
                application_log_path=str(same_log_file),
            )

            with self.assertRaises(SettingsError):
                save_settings(
                    settings,
                    Path(temporary_folder) / "settings.json",
                )

    def test_old_saved_log_setting_keeps_its_path(self) -> None:
        """Older settings keep their chosen log path after the setting is renamed."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            settings_path = Path(temporary_folder) / "settings.json"
            previous_log_path = (
                Path(temporary_folder) / "older-folder" / "activity.log"
            )
            settings_path.write_text(
                json.dumps({"activity_log_path": str(previous_log_path)}),
                encoding="utf-8",
            )

            settings = load_settings(settings_path)

        self.assertEqual(settings.api_activity_log_path, str(previous_log_path))

    def test_saving_settings_uses_the_new_api_log_setting_name(self) -> None:
        """New settings files should clearly name the API troubleshooting log."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            settings_path = Path(temporary_folder) / "settings.json"
            save_settings(AppSettings(), settings_path)
            saved_values = json.loads(settings_path.read_text(encoding="utf-8"))

        self.assertIn("api_activity_log_path", saved_values)
        self.assertIn("application_log_path", saved_values)
        self.assertNotIn("activity_log_path", saved_values)

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

    def test_load_settings_reports_text_that_is_not_utf8(self) -> None:
        """Unreadable settings text should become a clear settings error."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            settings_path = Path(temporary_folder) / "settings.json"
            settings_path.write_bytes(b"\xff")

            with self.assertRaisesRegex(SettingsError, "Could not read settings"):
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
