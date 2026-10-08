"""Check that test results are shown on screen and saved safely."""

from io import StringIO
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
from unittest.mock import patch

from config import AppSettings
from helpers import log_file_matches_saved_checksum
from run_tests import main
from run_tests import run_test_suite


class TestRunnerTests(unittest.TestCase):
    """Check the test runner's output and saved test report."""

    def test_runner_uses_the_tests_log_path_from_settings(self) -> None:
        """The saved tests log location should be used for each test run."""
        settings = AppSettings(tests_log_path="C:\\Logs\\my_tests_log")

        with (
            patch("run_tests.load_settings", return_value=settings),
            patch("run_tests.run_test_suite", return_value=0) as run_tests,
        ):
            result_code = main()

        self.assertEqual(result_code, 0)
        run_tests.assert_called_once_with(settings.tests_log_path)

    def make_test_file(self, tests_folder: Path, test_result: str) -> None:
        """Create one tiny passing or failing test for the runner to execute."""
        test_file = tests_folder / f"test_sample_{uuid4().hex}.py"
        test_file.write_text(
            "import unittest\n\n"
            "class ExampleTests(unittest.TestCase):\n"
            "    def test_example(self):\n"
            f"        self.assertTrue({test_result})\n",
            encoding="utf-8",
        )

    def test_test_results_are_shown_and_saved_with_a_checksum(self) -> None:
        """A test run should appear on screen and be kept in the tests log."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            work_folder = Path(temporary_folder)
            tests_folder = work_folder / "tests"
            tests_folder.mkdir()
            self.make_test_file(tests_folder, "True")
            tests_log_path = work_folder / "test-results" / "tests_log"
            screen = StringIO()

            result_code = run_test_suite(
                tests_log_path,
                tests_folder,
                screen,
            )

            screen_results = screen.getvalue()
            saved_results = tests_log_path.read_text(encoding="utf-8")

            self.assertEqual(result_code, 0)
            self.assertIn("Ran 1 test", screen_results)
            self.assertIn("OK", screen_results)
            self.assertIn("Ran 1 test", saved_results)
            self.assertIn("OK", saved_results)
            self.assertTrue(
                log_file_matches_saved_checksum(
                    tests_log_path,
                    Path(f"{tests_log_path}.sha256"),
                )
            )

    def test_failed_test_is_shown_and_saved_and_returns_failure(self) -> None:
        """A failing test should be written down and return a failure code."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            work_folder = Path(temporary_folder)
            tests_folder = work_folder / "tests"
            tests_folder.mkdir()
            self.make_test_file(tests_folder, "False")
            tests_log_path = work_folder / "tests_log"
            screen = StringIO()

            result_code = run_test_suite(
                tests_log_path,
                tests_folder,
                screen,
            )

            self.assertEqual(result_code, 1)
            self.assertIn("FAILED", screen.getvalue())
            self.assertIn("FAILED", tests_log_path.read_text(encoding="utf-8"))

    def test_later_test_run_is_added_after_earlier_results(self) -> None:
        """A new test run should keep the earlier results in the same log."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            work_folder = Path(temporary_folder)
            tests_folder = work_folder / "tests"
            tests_folder.mkdir()
            self.make_test_file(tests_folder, "True")
            tests_log_path = work_folder / "tests_log"

            first_run_code = run_test_suite(
                tests_log_path,
                tests_folder,
                StringIO(),
            )
            second_run_code = run_test_suite(
                tests_log_path,
                tests_folder,
                StringIO(),
            )
            saved_results = tests_log_path.read_text(encoding="utf-8")

            self.assertEqual(first_run_code, 0)
            self.assertEqual(second_run_code, 0)
            self.assertEqual(saved_results.count("Test run started:"), 2)
            self.assertEqual(saved_results.count("Ran 1 test"), 2)
            self.assertTrue(
                log_file_matches_saved_checksum(
                    tests_log_path,
                    Path(f"{tests_log_path}.sha256"),
                )
            )

    def test_results_still_run_when_the_tests_log_cannot_be_opened(self) -> None:
        """A bad log path should be explained without stopping the tests."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            work_folder = Path(temporary_folder)
            tests_folder = work_folder / "tests"
            tests_folder.mkdir()
            self.make_test_file(tests_folder, "True")
            screen = StringIO()

            result_code = run_test_suite(
                work_folder,
                tests_folder,
                screen,
            )

            self.assertEqual(result_code, 0)
            self.assertIn("could not be saved to the tests log", screen.getvalue())
            self.assertIn("Ran 1 test", screen.getvalue())
            self.assertIn("OK", screen.getvalue())


if __name__ == "__main__":
    unittest.main()
