"""Reusable NiceGUI widget builders shared across pages."""

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


def page_title(text: str) -> None:
    """Create a page heading styled with the BMD theme gradient."""

    ui.label(text).classes("text-3xl font-bold").style(
        "background: linear-gradient(135deg, #2ECC71, #0077B6); "
        "-webkit-background-clip: text; -webkit-text-fill-color: transparent;"
    )


def _text_input(
    label: str,
    value: str,
    placeholder: str | None,
    hint: str,
    required: bool,
) -> ui.input:
    """User input field widget builder."""

    with ui.column().classes("w-full gap-1 mt-3"):
        required_label(label) if required else optional_label(text=label)
        input_field = (
            ui.input(value=value, placeholder=placeholder)
            .props("outlined")
            .classes("w-full")
        )
        if hint:
            ui.label(hint).classes("text-xs text-gray-400 mt-1")
        return input_field


def required_text_input(
    label: str, value: str = "", placeholder: str | None = None, hint: str = ""
) -> ui.input:
    """A free text user input widget whose input is mandatory."""
    return _text_input(label, value, placeholder, hint, required=True)


def optional_text_input(
    label: str, value: str = "", placeholder: str | None = None, hint: str = ""
) -> ui.input:
    """A free text user input widget whose input is optional."""
    return _text_input(label, value, placeholder, hint, required=False)


def optional_textarea_input(
    label: str, placeholder: str | None = None, rows: int = 3
) -> ui.textarea:
    """A free textarea user input widget whose input is optional."""
    with ui.column().classes("w-full gap-1 mt-3"):
        optional_label(label)
        return (
            ui.textarea(placeholder=placeholder)
            .props(f"outlined rows={rows}")
            .classes("w-full")
        )


def password_input(label: str = "Password", placeholder: str | None = None) -> ui.input:
    """Password input widget - hides the entered characters."""

    with ui.column().classes("w-full gap-1 mt-3"):
        required_label(label)
        return (
            ui.input(placeholder=placeholder, password=True)
            .props("outlined")
            .classes("w-full")
        )


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
