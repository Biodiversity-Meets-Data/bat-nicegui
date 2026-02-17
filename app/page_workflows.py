"""Workflows list page."""

import json

from fastapi.responses import RedirectResponse
from nicegui import app, ui

from config import LOCAL_API_BASE_URL
from database import get_user_workflows
from ui_common import apply_bmd_theme, check_auth, create_footer, create_header


@ui.page("/workflows")
async def workflows_page():
    user_id = check_auth()
    if not user_id:
        return RedirectResponse("/login")

    apply_bmd_theme()
    ui.run_javascript("document.body.classList.remove('public-auth')")
    create_header("workflows")

    with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-6"):
        with ui.row().classes("w-full justify-between items-center"):
            ui.label("Your Workflows").classes("text-3xl font-bold").style(
                "background: linear-gradient(135deg, #2ECC71, #0077B6); "
                "-webkit-background-clip: text; -webkit-text-fill-color: transparent;"
            )
            ui.button("Refresh", on_click=lambda: ui.navigate.to("/workflows")).classes(
                "bmd-btn-secondary bmd-btn"
            ).props("icon=refresh")

        workflows = get_user_workflows(user_id)

        await ui.run_javascript(
            """
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
                document.querySelectorAll('[data-copy-id]').forEach((el) => {
                    if (el.dataset.copyBound) return;
                    el.dataset.copyBound = '1';
                    el.addEventListener('click', () => {
                        window.copyWorkflowId(el.dataset.copyId);
                    });
                });
            };
            """
        )

        if not workflows:
            with ui.card().classes("bmd-card p-8 w-full text-center"):
                ui.icon("science", size="4rem").classes("text-gray-300 mb-4")
                ui.label("No workflows submitted yet").classes("text-xl text-gray-500")
                ui.label("Create your first workflow to get started").classes(
                    "text-gray-400"
                )
                ui.button(
                    "+ New Workflow", on_click=lambda: ui.navigate.to("/select-workflow")
                ).classes("bmd-btn mt-4")
        else:
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

                for wf in workflows:
                    with ui.row().classes(
                        "w-full items-center py-3 border-b border-gray-100 gap-4"
                    ):
                        with ui.row().classes("w-32 items-center gap-2"):
                            ui.label(wf["workflow_id"][:12] + "...").classes(
                                "font-mono text-sm"
                            ).props(f'title="{wf["workflow_id"]}"')
                            ui.button(
                                icon="content_copy",
                                on_click=lambda: ui.notify(
                                    "Workflow ID copied", type="positive"
                                ),
                            ).props('flat round title="Copy ID"').classes(
                                "text-gray-500"
                            ).props(f"data-copy-id={json.dumps(wf['workflow_id'])}")
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
                                else "orange" if status == "submitted" else "red"
                            )
                        )
                        ui.badge(status.upper()).props(f"color={color}").classes("w-28")

                        ui.label(
                            wf["created_at"][:16] if wf["created_at"] else "N/A"
                        ).classes("w-36 text-sm text-gray-500")

                        with ui.row().classes("w-32 items-center gap-2"):
                            if status == "completed":
                                ui.button(
                                    "View",
                                    on_click=lambda wid=wf[
                                        "workflow_id"
                                    ]: ui.navigate.to(f"/results/{wid}"),
                                ).props("flat color=teal icon=visibility")

                            async def confirm_delete(
                                workflow_id=wf["workflow_id"], name=wf["name"]
                            ):
                                with ui.dialog() as dialog, ui.card().classes(
                                    "p-6 w-96"
                                ):
                                    ui.label("Delete Workflow").classes(
                                        "text-xl font-bold text-red-600 mb-2"
                                    )
                                    ui.label(
                                        f"Are you sure you want to permanently delete '{name}'?"
                                    ).classes("text-gray-700 mb-4")
                                    ui.label("This action cannot be undone.").classes(
                                        "text-sm text-gray-500 mb-4"
                                    )

                                    with ui.row().classes("justify-end gap-3"):
                                        ui.button(
                                            "Cancel", on_click=dialog.close
                                        ).props("flat")

                                        async def do_delete():
                                            token = app.storage.user.get("token")
                                            import httpx

                                            async with httpx.AsyncClient() as client:
                                                await client.delete(
                                                    f"{LOCAL_API_BASE_URL}/api/workflows/{workflow_id}",
                                                    headers={
                                                        "Authorization": f"Bearer {token}"
                                                    },
                                                )
                                            dialog.close()
                                            ui.notify(
                                                "Workflow deleted", type="positive"
                                            )
                                            ui.navigate.to("/workflows")

                                        ui.button(
                                            "Delete",
                                            on_click=do_delete,
                                        ).classes("bmd-btn-danger bmd-btn")

                                dialog.open()

                            ui.button(
                                icon="delete",
                                on_click=confirm_delete,
                            ).props("flat round color=red")
        await ui.run_javascript(
            "window.bindWorkflowIdCopyButtons && window.bindWorkflowIdCopyButtons();"
        )
    create_footer()
