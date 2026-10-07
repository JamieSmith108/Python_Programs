"""Prepare show details so they are easy to read on screen."""

from config import NOT_AVAILABLE, SHOW_FIELD_OPTIONS
from tvmaze_api import ProgramDetails


def format_program_details(
    program: ProgramDetails,
    selected_fields: tuple[str, ...],
) -> str:
    """Make a readable list containing only the fields the person selected."""
    result_lines = []

    for field_name, field_label in SHOW_FIELD_OPTIONS:
        if field_name not in selected_fields:
            continue

        field_value = program.fields.get(field_name, NOT_AVAILABLE)
        result_lines.append(f"{field_label}: {field_value}")

    return "\n\n".join(result_lines)
