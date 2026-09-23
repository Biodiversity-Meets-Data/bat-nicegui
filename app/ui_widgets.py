"""Reusable NiceGUI widget builders shared across pages."""

import enum
from typing import TypeVar

from nicegui import ui

E = TypeVar("E", bound=enum.Enum)


class Color(enum.StrEnum):
    GRAY = "text-gray-800"
    RED = "text-red-600"


class IntNumber(ui.number):
    """A number input restricted to integers that never stays empty.

    If the user clears the field, the default value is restored when the
    field loses focus, so the widget always holds an integer.
    """

    def __init__(self, value: int, min: int | None, max: int | None) -> None:
        super().__init__(
            value=value, min=min, max=max, step=1, precision=0, format="%d"
        )
        self._default = value
        self.on(type="blur", handler=self._restore_default_if_empty, args=[])

    def _restore_default_if_empty(self) -> None:
        if self.value is None:
            self.value = self._default

    @property
    def int_value(self) -> int:
        """The entered value as an int (the default if the field is empty)."""
        return self._default if self.value is None else int(self.value)


def required_label(text: str) -> None:
    """Add a label with required asterisk."""

    with ui.row().classes("items-center gap-0 mb-1"):
        ui.label(text).classes("field-label")
        ui.label("*").classes("required-asterisk")


def optional_label(text: str) -> None:
    """Add a label with optional hint."""

    with ui.row().classes("items-center gap-2 mb-1"):
        ui.label(text).classes("field-label")
        ui.label("(optional)").classes("optional-hint")


def page_title(text: str) -> None:
    """Add a page heading styled with the BMD theme gradient."""

    ui.label(text).classes("text-3xl font-bold").style(
        "background: linear-gradient(135deg, #2ECC71, #0077B6); "
        "-webkit-background-clip: text; -webkit-text-fill-color: transparent;"
    )


def card_header(text: str, color: Color = Color.GRAY) -> None:
    """Add a section/card header."""
    ui.label(text).classes(f"text-xl font-semibold {color}")


def _text_input(
    label: str,
    value: str,
    placeholder: str | None,
    hint: str,
    required: bool,
    readonly: bool = False,
) -> ui.input:
    """User free text input widget builder."""

    with ui.column().classes("w-full gap-1 mt-3"):
        required_label(label) if required else optional_label(text=label)
        input_field = (
            ui.input(value=value, placeholder=placeholder)
            .props("outlined" + (" readonly" if readonly else ""))
            .classes("w-full")
        )
        if readonly:
            input_field.classes("opacity-70 cursor-not-allowed")
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


def readonly_text_input(label: str, value: str = "", hint: str = "") -> ui.input:
    """A non-editable text field, for display of values the user may not change."""
    return _text_input(label, value, None, hint, required=True, readonly=True)


def required_int_input(
    label: str,
    min: int,
    max: int,
    value: int | None = None,
    hint: str = "",
) -> IntNumber:
    """A numeric input widget whose input is mandatory and restricted to
    integers within lower and upper bounds.

    The widget blocks values outside the bounds and rounds entered decimals to
    the nearest integer. The given 'value' is the default, restored if the
    field is left empty.
    """

    with ui.column().classes("w-full gap-1 mt-3"):
        required_label(label)
        number_field = (
            IntNumber(value=value if value is not None else min, min=min, max=max)
            .props("outlined")
            .classes("w-full")
        )
        if hint:
            ui.label(hint).classes("text-xs text-gray-400 mt-1")
        return number_field


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
