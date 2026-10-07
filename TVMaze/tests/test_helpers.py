"""Check that the shared helper functions handle common values."""

import unittest
import logging
from io import BytesIO
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from urllib.request import Request
from PIL import Image

from helpers import (
    DoNotFollowWebsiteRedirects,
    is_allowed_tvmaze_api_address,
    is_allowed_tvmaze_image_address,
    is_allowed_tvmaze_request_address,
    log_file_matches_saved_checksum,
    make_file_checksum,
    make_english_label,
    make_english_value,
    make_one_line,
    make_scrollable_frame,
    make_small_picture,
    open_trusted_tvmaze_request,
    read_whole_number,
    read_text,
    remove_html_tags,
    save_log_checksum,
    show_read_only_text_window,
    start_rotating_file_log,
    stop_rotating_file_log,
)


class HelperFunctionTests(unittest.TestCase):
    """Check the small functions used to prepare TVMaze information."""

    def test_read_text_trims_spaces(self) -> None:
        """Text values should not keep spaces around the words."""
        self.assertEqual(read_text("  Doctor Who  "), "Doctor Who")

    def test_read_text_uses_fallback_for_empty_value(self) -> None:
        """An empty value should use the helpful default message."""
        self.assertEqual(read_text("   "), "Not available")

    def test_read_whole_number_explains_bad_settings_text(self) -> None:
        """A bad number should name the box that needs to be fixed."""
        with self.assertRaisesRegex(ValueError, "Window width must be a whole number"):
            read_whole_number("Window width", "wide")

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

    def test_only_trusted_tvmaze_web_addresses_are_allowed(self) -> None:
        """Only the real TVMaze search and picture links should pass the check."""
        good_api_address = "https://api.tvmaze.com/singlesearch/shows"
        good_search_address = (
            "https://api.tvmaze.com/singlesearch/shows?q=Doctor+Who"
        )
        good_matching_list_address = (
            "https://api.tvmaze.com/search/shows?q=Doctor+Who"
        )
        good_picture_address = (
            "https://static.tvmaze.com/uploads/images/medium_portrait/0/1.jpg"
        )

        self.assertTrue(is_allowed_tvmaze_api_address(good_api_address))
        self.assertTrue(is_allowed_tvmaze_request_address(good_search_address))
        self.assertTrue(
            is_allowed_tvmaze_request_address(good_matching_list_address)
        )
        self.assertTrue(is_allowed_tvmaze_image_address(good_picture_address))
        self.assertTrue(is_allowed_tvmaze_request_address(good_picture_address))

        too_large_search_address = (
            "https://api.tvmaze.com/singlesearch/shows?q="
            + ("A" * 2500)
        )
        unsafe_addresses = (
            "http://api.tvmaze.com/singlesearch/shows?q=Doctor",
            "https://api.tvmaze.com.evil.example/singlesearch/shows?q=Doctor",
            "https://api.tvmaze.com@evil.example/singlesearch/shows?q=Doctor",
            "https://api.tvmaze.com:444/singlesearch/shows?q=Doctor",
            "https://api.tvmaze.com/singlesearch/shows?next=evil",
            "https://api.tvmaze.com/singlesearch/shows?q=one&q=two",
            "https://api.tvmaze.com/singlesearch/shows?q=",
            too_large_search_address,
            "https://static.tvmaze.com.evil.example/uploads/images/1.jpg",
            "https://static.tvmaze.com/uploads/images/1.svg",
            "https://static.tvmaze.com/uploads/images/../private/1.jpg",
            "https://static.tvmaze.com/uploads/images/%2e%2e/private/1.jpg",
            "https://static.tvmaze.com/uploads/images/1.jpg#",
        )

        for unsafe_address in unsafe_addresses:
            with self.subTest(address=unsafe_address):
                self.assertFalse(
                    is_allowed_tvmaze_request_address(unsafe_address)
                )

    def test_untrusted_address_does_not_start_a_web_request(self) -> None:
        """The network helper should stop unsafe addresses before connecting."""
        with patch("helpers.build_opener") as make_opener:
            with self.assertRaisesRegex(ValueError, "not an approved"):
                open_trusted_tvmaze_request(
                    Request("https://evil.example/collect"),
                    10,
                )

        make_opener.assert_not_called()

    def test_picture_helper_makes_a_smaller_copy(self) -> None:
        """The same image helper should shrink pictures for every window."""
        picture_stream = BytesIO()
        Image.new("RGB", (500, 400), color="blue").save(
            picture_stream,
            format="JPEG",
        )

        small_picture = make_small_picture(picture_stream.getvalue(), (90, 125))

        self.assertLessEqual(small_picture.width, 90)
        self.assertLessEqual(small_picture.height, 125)

    def test_log_checksum_detects_contents_changed_outside_the_app(self) -> None:
        """A changed log should no longer match the app's saved checksum."""
        with tempfile.TemporaryDirectory() as folder:
            log_file = Path(folder) / "application_log"
            checksum_file = Path(f"{log_file}.sha256")
            log_file.write_text("First note.\n", encoding="utf-8")
            save_log_checksum(log_file, checksum_file)

            self.assertTrue(
                log_file_matches_saved_checksum(log_file, checksum_file)
            )
            log_file.write_text("First note.\nChanged outside the app.\n", encoding="utf-8")

            self.assertFalse(
                log_file_matches_saved_checksum(log_file, checksum_file)
            )
            self.assertEqual(len(make_file_checksum(log_file)), 64)

    def test_app_log_updates_checksum_when_app_adds_a_note(self) -> None:
        """The checksum must follow normal app writes, not report them as edits."""
        with tempfile.TemporaryDirectory() as folder:
            log_file = Path(folder) / "application_log"
            checksum_file = Path(f"{log_file}.sha256")
            start_rotating_file_log(
                "checksum_test_logger",
                log_file,
                "Logging has started.",
                "Log saved in:",
            )
            try:
                logger = logging.getLogger("checksum_test_logger")
                logger.info("A new note from inside the app.")

                self.assertTrue(
                    log_file_matches_saved_checksum(log_file, checksum_file)
                )
            finally:
                stop_rotating_file_log("checksum_test_logger")

    def test_app_does_not_hide_a_change_made_outside_the_app(self) -> None:
        """The app must not save a new checksum over outside changes."""
        with tempfile.TemporaryDirectory() as folder:
            log_file = Path(folder) / "application_log"
            checksum_file = Path(f"{log_file}.sha256")
            start_rotating_file_log(
                "changed_log_test_logger",
                log_file,
                "Logging has started.",
                "Log saved in:",
            )
            try:
                log_file.write_text(
                    "Someone changed this log outside the app.\n",
                    encoding="utf-8",
                )
                saved_checksum_before_app_note = checksum_file.read_text(
                    encoding="ascii"
                )
                logging.getLogger("changed_log_test_logger").warning(
                    "The app added another note."
                )

                self.assertFalse(
                    log_file_matches_saved_checksum(log_file, checksum_file)
                )
                self.assertEqual(
                    checksum_file.read_text(encoding="ascii"),
                    saved_checksum_before_app_note,
                )
            finally:
                stop_rotating_file_log("changed_log_test_logger")

    def test_scrollable_frame_helper_connects_contents_and_scrollbar(self) -> None:
        """Both scrollable lists should use the same tested setup."""
        parent = object()

        with (
            patch("helpers.tk.Canvas") as make_canvas,
            patch("helpers.ttk.Scrollbar") as make_scrollbar,
            patch("helpers.ttk.Frame") as make_frame,
        ):
            canvas = make_canvas.return_value
            contents = make_frame.return_value
            canvas.create_window.return_value = 42

            returned_canvas, returned_contents = make_scrollable_frame(
                parent,
                height=190,
            )

            content_configure_callback = contents.bind.call_args.args[1]
            content_configure_callback(
                SimpleNamespace(widget=contents)
            )
            canvas_configure_callback = canvas.bind.call_args.args[1]
            canvas_configure_callback(SimpleNamespace(width=360))

        self.assertIs(returned_canvas, canvas)
        self.assertIs(returned_contents, contents)
        make_canvas.assert_called_once_with(
            parent,
            highlightthickness=0,
            height=190,
        )
        canvas.configure.assert_any_call(
            yscrollcommand=make_scrollbar.return_value.set
        )
        canvas.configure.assert_any_call(
            scrollregion=canvas.bbox.return_value
        )
        self.assertEqual(canvas.configure.call_count, 2)
        canvas.itemconfigure.assert_called_once_with(42, width=360)

    def test_unreasonable_wait_limit_does_not_start_a_web_request(self) -> None:
        """A website request must use a sensible wait limit."""
        with patch("helpers.build_opener") as make_opener:
            with self.assertRaisesRegex(ValueError, "from 1 to 120 seconds"):
                open_trusted_tvmaze_request(
                    Request(
                        "https://api.tvmaze.com/singlesearch/shows?q=Doctor"
                    ),
                    121,
                )

        make_opener.assert_not_called()

    def test_longest_allowed_wait_limit_is_passed_to_the_web_request(self) -> None:
        """A wait limit of 120 seconds is the longest permitted value."""
        with patch("helpers.build_opener") as make_opener:
            opener = make_opener.return_value
            open_trusted_tvmaze_request(
                Request(
                    "https://api.tvmaze.com/singlesearch/shows?q=Doctor"
                ),
                120,
            )

        opener.open.assert_called_once()
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 120)

    def test_redirects_are_never_followed(self) -> None:
        """A trusted server must not redirect the program to another website."""
        redirect_guard = DoNotFollowWebsiteRedirects()
        request = Request(
            "https://api.tvmaze.com/singlesearch/shows?q=Doctor"
        )

        redirect = redirect_guard.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://evil.example/collect",
        )

        self.assertIsNone(redirect)

    def test_log_viewer_displays_notes_without_editing_them(self) -> None:
        """Log contents should be visible while the text box stays locked."""
        with (
            patch("helpers.tk.Toplevel") as make_window,
            patch("helpers.ttk.Label") as make_label,
            patch("helpers.ttk.Frame"),
            patch("helpers.tk.Text") as make_text,
            patch("helpers.ttk.Scrollbar"),
        ):
            text_window = show_read_only_text_window(
                object(),
                "Read API issue log",
                "The request worked.",
            )

        self.assertIs(text_window, make_window.return_value)
        make_text.return_value.insert.assert_called_once_with(
            "1.0",
            "The request worked.",
        )
        make_text.return_value.configure.assert_called_with(state="disabled")
        self.assertEqual(make_text.return_value.bind.call_count, 4)
        self.assertIn("read-only", make_label.call_args.kwargs["text"])

    def test_log_viewer_warns_that_the_file_was_changed_outside_the_app(self) -> None:
        """The reader should see a clear warning after a checksum mismatch."""
        with (
            patch("helpers.tk.Toplevel"),
            patch("helpers.ttk.Label") as make_label,
            patch("helpers.ttk.Frame"),
            patch("helpers.tk.Text"),
            patch("helpers.ttk.Scrollbar"),
        ):
            show_read_only_text_window(
                object(),
                "Read application log",
                "A changed note.",
                outside_change_was_found=True,
            )

        self.assertIn("changed outside this program", make_label.call_args.kwargs["text"])

    def test_log_viewer_warns_if_someone_tries_to_amend_a_log(self) -> None:
        """Typing or pasting must warn the reader and leave the log unchanged."""
        with (
            patch("helpers.tk.Toplevel"),
            patch("helpers.ttk.Label"),
            patch("helpers.ttk.Frame"),
            patch("helpers.tk.Text") as make_text,
            patch("helpers.ttk.Scrollbar"),
            patch("helpers.messagebox.showwarning") as show_warning,
        ):
            show_read_only_text_window(object(), "Read log", "Saved note.")

            keyboard_callback = make_text.return_value.bind.call_args_list[0].args[1]
            edit_result = keyboard_callback(
                SimpleNamespace(
                    keysym="x",
                    char="x",
                )
            )
            keyboard_callback(SimpleNamespace(keysym="y", char="y"))
            paste_callback = make_text.return_value.bind.call_args_list[1].args[1]
            paste_result = paste_callback(
                SimpleNamespace(keysym="??", char=""),
            )

        self.assertEqual(edit_result, "break")
        self.assertEqual(paste_result, "break")
        show_warning.assert_called_once()


    def test_close_logger_handlers_removes_open_handlers(self) -> None:
        """A closed logger should no longer keep its handlers."""
        logger = logging.getLogger("helper_test_logger")
        logger.addHandler(logging.NullHandler())

        stop_rotating_file_log("helper_test_logger")

        self.assertEqual(logger.handlers, [])


if __name__ == "__main__":
    unittest.main()
