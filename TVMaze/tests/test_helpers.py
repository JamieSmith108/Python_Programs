"""Check that the shared helper functions handle common values."""

import unittest
import logging

from helpers import (
    close_logger_handlers,
    make_english_label,
    make_english_value,
    make_one_line,
    read_text,
    remove_html_tags,
)


class HelperFunctionTests(unittest.TestCase):
    """Check the small functions used to prepare TVMaze information."""

    def test_read_text_trims_spaces(self) -> None:
        """Text values should not keep spaces around the words."""
        self.assertEqual(read_text("  Doctor Who  "), "Doctor Who")

    def test_read_text_uses_fallback_for_empty_value(self) -> None:
        """An empty value should use the helpful default message."""
        self.assertEqual(read_text("   "), "Not available")

    def test_remove_html_tags_keeps_summary_words(self) -> None:
        """The summary should stay readable after its HTML is removed."""
        self.assertEqual(
            remove_html_tags("<p>A <b>good</b> show.</p><p>More words.</p>"),
            "A good show. More words.",
        )

    def test_make_english_label_spells_out_field_names(self) -> None:
        """A technical name should become an ordinary English label."""
        self.assertEqual(make_english_label("averageRuntime"), "Average episode length")

    def test_make_english_value_reads_nested_details(self) -> None:
        """A nested answer should be readable without braces or quotes."""
        readable_value = make_english_value(
            {
                "name": "BBC One",
                "country": {"name": "United Kingdom", "code": "GB"},
            }
        )

        self.assertEqual(
            readable_value,
            "BBC One\nCountry: United Kingdom\nCode: GB",
        )
        self.assertNotIn("{", readable_value)

    def test_make_one_line_removes_line_breaks_and_limits_length(self) -> None:
        """A long message should fit on one short line."""
        self.assertEqual(make_one_line("  first\n second  ", 10), "first seco")

    def test_close_logger_handlers_removes_open_handlers(self) -> None:
        """A closed logger should no longer keep its handlers."""
        logger = logging.getLogger("helper_test_logger")
        logger.addHandler(logging.NullHandler())

        close_logger_handlers(logger)

        self.assertEqual(logger.handlers, [])


if __name__ == "__main__":
    unittest.main()
