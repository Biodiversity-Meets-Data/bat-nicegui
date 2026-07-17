"""Workflows page: lists the workflows that are run by the user."""

import functools
import json
from typing import Any

import httpx
from fastapi.responses import RedirectResponse
from nicegui import app, ui

from config import LOCAL_API_BASE_URL
from database import get_user_workflows
from ui_common import apply_bmd_theme, check_auth, PageHeader
from ui_widgets import page_title


class UserWorkflowsPage:
    """Page listing the current user's submitted BAT workflows.

    Instantiated once per visit (inside the page handler), after the user has
    been authenticated and their workflows fetched.
    """

    ROUTE = "/workflows"

    def __init__(self, user_id: str, workflows: list[dict[str, Any]]) -> None:
        self.user_id = user_id
        self.workflows = workflows
        self.build_page()

    # ------------------------- Page construction --------------------------- #

    def build_page(self) -> None:
        """Build the page: header plus either the empty state or the table."""

        with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-6"):
            # Add page main header and refresh button.
            with ui.row().classes("w-full justify-between items-center"):
                page_title("Your Workflows")
                ui.button(
                    "Refresh", on_click=lambda: ui.navigate.to("/workflows")
                ).classes("bmd-btn-secondary bmd-btn").props("icon=refresh")

            # Add list of workflows launched by the user.
            if not self.workflows:
                self.add_empty_state()
            else:
                self.add_workflow_table()

    def add_empty_state(self) -> None:
        """Build the placeholder card shown when the user has no workflows."""

        with ui.card().classes("bmd-card p-8 w-full text-center"):
            ui.icon("science", size="4rem").classes("text-gray-300 mb-4")
            ui.label("No workflows submitted yet").classes("text-xl text-gray-500")
            ui.label("Create your first workflow to get started").classes(
                "text-gray-400"
            )
            ui.button(
                "+ New Workflow",
                on_click=lambda: ui.navigate.to("/select-workflow"),
            ).classes("bmd-btn mt-4")

    def add_workflow_table(self) -> None:
        """Build the table card: column headers plus one row per workflow."""

        with ui.card().classes("bmd-card p-6 w-full"):
            with ui.row().classes(
                "w-full items-center py-3 border-b-2 border-gray-200 gap-4 font-semibold text-gray-600"
            ):
                ui.label("ID").classes("w-32")
                ui.label("Name").classes("flex-1")
                ui.label("Species").classes("w-24")
                ui.label("Ecosystem").classes("w-28")
                ui.label("Status").classes("w-28")
                ui.label("Created").classes("w-36")
                ui.label("Actions").classes("w-32")

            for wf in self.workflows:
                self.add_workflow_row(wf)

    def add_workflow_row(self, wf: dict[str, Any]) -> None:
        """Build a single workflow row: id, metadata, status, and actions."""

        with ui.row().classes(
            "w-full items-center py-3 border-b border-gray-100 gap-4"
        ):
            with ui.row().classes("w-32 items-center gap-2"):
                ui.label(wf["workflow_id"][:12] + "...").classes(
                    "font-mono text-sm"
                ).props(f'title="{wf["workflow_id"]}"')
                ui.button(
                    icon="content_copy",
                    on_click=lambda: ui.notify("Workflow ID copied", type="positive"),
                ).props('flat round title="Copy ID"').classes("text-gray-500").props(
                    f"data-copy-to-clipboard-id={json.dumps(wf['workflow_id'])}"
                )

            # Add workflow details field.
            ui.label(wf["name"]).classes("font-semibold flex-1")
            ui.label(wf.get("species_name") or "-").classes("w-24")
            ecosystem = (wf.get("ecosystem_type") or "unknown").lower()
            ecosystem_color = (
                "green"
                if ecosystem == "terrestrial"
                else ("blue" if ecosystem == "freshwater" else "grey")
            )
            ui.badge(ecosystem.upper()).props(f"color={ecosystem_color}").classes(
                "w-28"
            )
            status = wf["status"]
            color = (
                "green"
                if status == "completed"
                else (
                    "blue"
                    if status == "running"
                    else "orange"
                    if status == "submitted"
                    else "red"
                )
            )
            ui.badge(status.upper()).props(f"color={color}").classes("w-28")

            ui.label(wf["created_at"][:16] if wf["created_at"] else "N/A").classes(
                "w-36 text-sm text-gray-500"
            )

            with ui.row().classes("w-32 items-center gap-2"):
                if status == "completed":
                    ui.button(
                        "View",
                        on_click=lambda wid=wf["workflow_id"]: ui.navigate.to(
                            f"/results/{wid}"
                        ),
                    ).props("flat color=teal icon=visibility")

                ui.button(
                    icon="delete",
                    on_click=functools.partial(
                        self.confirm_workflow_deletion, wf["workflow_id"], wf["name"]
                    ),
                ).props("flat round color=red")

    # -------------------------- Event handlers ----------------------------- #

    async def confirm_workflow_deletion(self, workflow_id: str, name: str) -> None:
        """Open a confirmation dialog for deleting a single workflow."""

        with ui.dialog() as dialog, ui.card().classes("p-6 w-96"):
            ui.label("Delete Workflow").classes("text-xl font-bold text-red-600 mb-2")
            ui.label(f"Are you sure you want to permanently delete '{name}'?").classes(
                "text-gray-700 mb-4"
            )
            ui.label("This action cannot be undone.").classes(
                "text-sm text-gray-500 mb-4"
            )

            with ui.row().classes("justify-end gap-3"):
                ui.button("Cancel", on_click=dialog.close).props("flat")

                # The dialog is transient to this interaction, so its confirm
                # handler stays local rather than becoming a method.
                async def do_delete() -> None:
                    token = app.storage.user.get("token")
                    async with httpx.AsyncClient() as client:
                        await client.delete(
                            f"{LOCAL_API_BASE_URL}/api/workflows/{workflow_id}",
                            headers={"Authorization": f"Bearer {token}"},
                        )
                    dialog.close()
                    ui.notify("Workflow deleted", type="positive")
                    ui.navigate.to("/workflows")

                ui.button("Delete", on_click=do_delete).classes(
                    "bmd-btn-danger bmd-btn"
                )

        dialog.open()

    # ------------------ Client-side (browser) setup ------------------------ #

    async def initialize_clipboard_copy(self) -> None:
        """Inject the clipboard helper and bind it to the copy buttons.

        Runs after the widgets are built: the helper is defined on the client
        and then attached to every copy button rendered in the table.
        """
        await ui.run_javascript(COPY_TO_CLIPBOARD_JS)
        await ui.run_javascript(
            "window.bindWorkflowIdCopyButtons && window.bindWorkflowIdCopyButtons();"
        )

    # ---------------------- Page Route registration ------------------------ #

    @classmethod
    def register(cls) -> None:
        """Register the page's route.

        Add <cls>.register() at the end of the page's module so that the
        method gets called when the module is imported.
        """

        @ui.page(cls.ROUTE)
        async def _render_page() -> RedirectResponse | None:
            # Page is only accessible to authenticated users.
            user_id = check_auth()
            if not user_id:
                return RedirectResponse("/login")

            # Add base page styling (theme).
            apply_bmd_theme(header=PageHeader.WORKFLOW_PAGE)

            # Build the page by creating a new instance of the class, then wire
            # up the client-side clipboard-copy behaviour.
            page = cls(user_id, workflows=get_user_workflows(user_id))
            await page.initialize_clipboard_copy()
            return None


# Client-side clipboard helpers for the workflow-ID copy buttons. Defines two
# globals: one that copies a given string to the clipboard, and one that
# attaches the copy-to-clipboard action to every element tagged with a
# data-copy-to-clipboard-id attribute.
COPY_TO_CLIPBOARD_JS = """
    window.copyWorkflowId = async (text) => {
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(text);
                return;
            }
        } catch (err) {}
        const el = document.createElement('textarea');
        el.value = text;
        el.setAttribute('readonly', '');
        el.style.position = 'fixed';
        el.style.left = '-9999px';
        document.body.appendChild(el);
        el.select();
        try { document.execCommand('copy'); } catch (err) {}
        document.body.removeChild(el);
    };
    window.bindWorkflowIdCopyButtons = () => {
        document.querySelectorAll('[data-copy-to-clipboard-id]').forEach((el) => {
            if (el.dataset.copyBound) return;
            el.dataset.copyBound = '1';
            el.addEventListener('click', () => {
                window.copyWorkflowId(el.dataset.copyToClipboardId);
            });
        });
    };
"""

UserWorkflowsPage.register()
