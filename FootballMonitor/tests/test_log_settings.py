"""Check external settings defaults, saving, and safe log path choices."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from log_settings import (
    LogFileSettings,
    SettingsError,
    get_default_log_settings,
    get_settings_file_path,
    load_log_settings,
    save_log_settings,
    validate_log_settings,
)


class LogSettingsTests(unittest.TestCase):
    """Check that log settings stay outside the source folder and can be reused."""

    def test_default_logs_are_stored_in_the_external_user_folder(self) -> None:
        """Default log files should be placed under the user's local app data."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            with patch.dict(
                os.environ,
                {
                    "APPDATA": str(Path(temporary_folder) / "Roaming"),
                    "LOCALAPPDATA": str(Path(temporary_folder) / "Local"),
                },
            ):
                settings = get_default_log_settings()

        self.assertIn("FootballMonitor", settings.application_log)
        self.assertIn("Logs", settings.testing_log)
        self.assertNotIn("Python_Programs", settings.api_communications_log)

    def test_saved_paths_are_loaded_from_external_json_settings(self) -> None:
        """The cog settings can be kept between app launches in a JSON file."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            roaming_folder = Path(temporary_folder) / "Roaming"
            local_folder = Path(temporary_folder) / "Local"
            with patch.dict(
                os.environ,
                {
                    "APPDATA": str(roaming_folder),
                    "LOCALAPPDATA": str(local_folder),
                },
            ):
                expected_settings = LogFileSettings(
                    str(local_folder / "api.txt"),
                    str(local_folder / "app.txt"),
                    str(local_folder / "tests.txt"),
                )
                save_log_settings(expected_settings)
                loaded_settings = load_log_settings()
                saved_json = json.loads(
                    get_settings_file_path().read_text(encoding="utf-8")
                )

        self.assertEqual(loaded_settings, expected_settings)
        self.assertEqual(
            saved_json["application_log"],
            str(Path(expected_settings.application_log).resolve()),
        )

    def test_duplicate_log_paths_are_rejected(self) -> None:
        """Each type of log must be kept in its own file."""
        same_path = str(Path.home() / "football_log.txt")
        with self.assertRaisesRegex(SettingsError, "different file"):
            validate_log_settings(
                LogFileSettings(same_path, same_path, same_path)
            )

    def test_log_paths_inside_the_program_folder_are_rejected(self) -> None:
        """The log writer must not place log files beside the app source."""
        inside_code_folder = str(Path(__file__).resolve().parents[1] / "log.txt")
        with self.assertRaisesRegex(SettingsError, "outside"):
            validate_log_settings(
                LogFileSettings(
                    inside_code_folder,
                    str(Path.home() / "football_app.txt"),
                    str(Path.home() / "football_tests.txt"),
                )
            )


if __name__ == "__main__":
    unittest.main()
