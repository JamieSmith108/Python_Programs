"""Check separate log output, request details, and log tamper detection."""

import json
import logging
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import Mock, patch

import logging_service
from logging_service import (
    IntegrityCheckedFileHandler,
    check_log_file_integrity,
    log_api_communication,
    log_test_results,
    prepare_integrity_record,
)


class LoggingServiceTests(unittest.TestCase):
    """Check that log entries are useful and changed files are detected."""

    def test_api_log_record_has_request_reply_status_and_correlation_id(self) -> None:
        """The API log should keep every requested communication field."""
        fake_logger = Mock()
        with patch(
            "logging_service.logging.getLogger",
            return_value=fake_logger,
        ):
            log_api_communication(
                "GET",
                "https://site.api.espn.com/scoreboard",
                '{"events":[]}',
                200,
                "test-correlation-id",
            )

        logged_record = json.loads(fake_logger.info.call_args.args[0])
        self.assertEqual(logged_record["communication_type"], "GET")
        self.assertEqual(
            logged_record["requested"],
            "https://site.api.espn.com/scoreboard",
        )
        self.assertEqual(logged_record["returned"], '{"events":[]}')
        self.assertEqual(logged_record["http_status_code"], 200)
        self.assertEqual(
            logged_record["correlation_id"],
            "test-correlation-id",
        )

    def test_test_log_receives_the_complete_test_output(self) -> None:
        """The testing log call should receive every line from a test run."""
        fake_logger = Mock()
        full_results = "test_first ... ok\ntest_second ... FAIL\n"
        with patch(
            "logging_service.logging.getLogger",
            return_value=fake_logger,
        ):
            log_test_results(full_results)

        self.assertEqual(fake_logger.info.call_args.args[1], full_results.rstrip())

    def test_checksum_detects_a_log_file_changed_outside_the_program(self) -> None:
        """Changing saved log text by hand should make its checksum fail."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            folder_path = Path(temporary_folder)
            log_path = folder_path / "api_log.txt"
            manifest_path = folder_path / "checksums.json"
            with patch.object(
                logging_service,
                "_integrity_manifest_path",
                manifest_path,
            ), patch.object(logging_service, "_integrity_warnings", []):
                self.assertTrue(
                    prepare_integrity_record(
                        "api_communications_log",
                        log_path,
                    )
                )
                log_handler = IntegrityCheckedFileHandler(
                    "api_communications_log",
                    log_path,
                )
                temporary_logger = logging.Logger("temporary_api_logger")
                temporary_logger.addHandler(log_handler)
                temporary_logger.info("An API reply was saved.")
                temporary_logger.removeHandler(log_handler)
                log_handler.close()

                self.assertTrue(
                    check_log_file_integrity(
                        "api_communications_log",
                        str(log_path),
                    )
                )
                with self.assertRaises(PermissionError):
                    with log_path.open("a", encoding="utf-8"):
                        pass
                os.chmod(log_path, stat.S_IREAD | stat.S_IWRITE)
                with log_path.open("a", encoding="utf-8") as changed_log:
                    changed_log.write("This line was added outside the app.\n")

                self.assertFalse(
                    check_log_file_integrity(
                        "api_communications_log",
                        str(log_path),
                    )
                )
                contents_after_external_change = log_path.read_text(
                    encoding="utf-8"
                )
                refusal_handler = IntegrityCheckedFileHandler(
                    "api_communications_log",
                    log_path,
                )
                temporary_logger.addHandler(refusal_handler)
                temporary_logger.info("This must not be added after tampering.")
                temporary_logger.removeHandler(refusal_handler)
                refusal_handler.close()
                self.assertEqual(
                    log_path.read_text(encoding="utf-8"),
                    contents_after_external_change,
                )
                os.chmod(log_path, stat.S_IREAD | stat.S_IWRITE)


if __name__ == "__main__":
    unittest.main()
