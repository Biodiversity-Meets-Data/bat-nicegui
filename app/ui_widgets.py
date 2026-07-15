"""Reusable NiceGUI input-widget builders shared across pages."""

from enum import Enum
from typing import TypeVar

from nicegui import ui

E = TypeVar("E", bound=Enum)


def required_label(text: str) -> None:
    """Create a label with required asterisk."""

    with ui.row().classes("items-center gap-0 mb-1"):
        ui.label(text).classes("field-label")
        ui.label("*").classes("required-asterisk")


def optional_label(text: str) -> None:
    """Create a label with optional hint."""

    with ui.row().classes("items-center gap-2 mb-1"):
        ui.label(text).classes("field-label")
        ui.label("(optional)").classes("optional-hint")


def drop_down_menu(label: str, choices: type[E], default: E) -> ui.select:
    """Add a labeled drop-down menu whose options are the members/variants
    of an Enum. Each option's text is the variant's value.
    """

    with ui.column().classes("w-full gap-1 mt-4"):
        required_label(label)
        return (
            ui.select(
                options={member: member.value for member in choices},
                value=default,
            )
            .props("outlined")
            .classes("w-full")
        )
