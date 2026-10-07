"""Check that the shared helper functions handle common values."""

import unittest

from helpers import read_nested_text, read_number, read_text, read_text_list, remove_html_tags


class HelperFunctionTests(unittest.TestCase):
    """Check the small functions used to prepare TVMaze information."""

    def test_read_text_trims_spaces(self) -> None:
        """Text values should not keep spaces around the words."""
        self.assertEqual(read_text("  Doctor Who  "), "Doctor Who")

    def test_read_text_uses_fallback_for_empty_value(self) -> None:
        """An empty value should use the helpful default message."""
        self.assertEqual(read_text("   "), "Not available")

    def test_read_number_rejects_boolean_values(self) -> None:
        """A true or false value should not be treated as a rating."""
        self.assertIsNone(read_number(True))

    def test_read_text_list_joins_words(self) -> None:
        """A list of genres should become one readable line."""
        self.assertEqual(read_text_list(["Drama", "Comedy"]), "Drama, Comedy")

    def test_read_nested_text_finds_value(self) -> None:
        """A channel name inside a dictionary should be readable."""
        self.assertEqual(read_nested_text({"name": "BBC One"}, "name"), "BBC One")

    def test_remove_html_tags_keeps_summary_words(self) -> None:
        """The summary should stay readable after its HTML is removed."""
        self.assertEqual(
            remove_html_tags("<p>A <b>good</b> show.</p><p>More words.</p>"),
            "A good show. More words.",
        )


if __name__ == "__main__":
    unittest.main()
