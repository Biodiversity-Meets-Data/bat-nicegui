"""Account settings page."""

from fastapi.responses import RedirectResponse
from nicegui import app, ui

from auth_utils import hash_password, verify_password
from database import (
    check_email_exists,
    delete_user,
    get_user_by_id,
    update_user,
)
from ui_common import (
    apply_bmd_theme,
    check_auth,
    create_footer,
    create_header,
    optional_label,
    required_label,
)


@ui.page("/account")
async def account_page():
    user_id = check_auth()
    if not user_id:
        return RedirectResponse("/login")

    apply_bmd_theme()
    ui.run_javascript("document.body.classList.remove('public-auth')")
    create_header("account")

    user = get_user_by_id(user_id)
    if not user:
        ui.label("User not found").classes("text-xl text-red-500")
        create_footer()
        return

    with ui.column().classes("w-full max-w-2xl mx-auto p-6 gap-6"):
        ui.label("Account Settings").classes("text-3xl font-bold").style(
            "background: linear-gradient(135deg, #2ECC71, #0077B6); "
            "-webkit-background-clip: text; -webkit-text-fill-color: transparent;"
        )

        with ui.card().classes("bmd-card p-6 w-full"):
            ui.label("Profile Information").classes(
                "text-xl font-semibold text-gray-800 mb-4"
            )

            with ui.column().classes("w-full gap-1"):
                required_label("Full Name")
                name_input = (
                    ui.input(value=user.get("name", ""))
                    .props("outlined")
                    .classes("w-full")
                )

            with ui.column().classes("w-full gap-1 mt-4"):
                required_label("Email")
                email_input = (
                    ui.input(value=user.get("email", ""))
                    .props("outlined")
                    .classes("w-full")
                )

            with ui.column().classes("w-full gap-1 mt-4"):
                optional_label("ORCID")
                orcid_input = (
                    ui.input(value=user.get("orcid", "") or "")
                    .props("outlined")
                    .classes("w-full")
                )
                ui.label("Your ORCID identifier (format: 0000-0000-0000-0000)").classes(
                    "text-xs text-gray-400 mt-1"
                )

            async def save_profile():
                name = name_input.value.strip()
                email = email_input.value.strip()
                orcid = orcid_input.value.strip() if orcid_input.value else None

                if not name or not email:
                    ui.notify("Name and email are required", type="negative")
                    return

                if check_email_exists(email, exclude_user_id=user_id):
                    ui.notify("Email is already in use", type="negative")
                    return

                if orcid:
                    import re

                    orcid_pattern = r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$"
                    if not re.match(orcid_pattern, orcid):
                        ui.notify("Invalid ORCID format", type="negative")
                        return

                update_user(
                    user_id, name=name, email=email, orcid=orcid if orcid else ""
                )
                app.storage.user["user_name"] = name
                ui.notify("Profile updated successfully", type="positive")

            ui.button("Save Changes", on_click=save_profile).classes("bmd-btn mt-6")

        with ui.card().classes("bmd-card p-6 w-full"):
            ui.label("Change Password").classes(
                "text-xl font-semibold text-gray-800 mb-4"
            )

            with ui.column().classes("w-full gap-1"):
                required_label("Current Password")
                current_pw_input = (
                    ui.input(placeholder="Enter current password", password=True)
                    .props("outlined")
                    .classes("w-full")
                )

            with ui.column().classes("w-full gap-1 mt-4"):
                required_label("New Password")
                new_pw_input = (
                    ui.input(placeholder="At least 6 characters", password=True)
                    .props("outlined")
                    .classes("w-full")
                )

            with ui.column().classes("w-full gap-1 mt-4"):
                required_label("Confirm New Password")
                confirm_pw_input = (
                    ui.input(placeholder="Repeat new password", password=True)
                    .props("outlined")
                    .classes("w-full")
                )

            async def change_password():
                current_pw = current_pw_input.value
                new_pw = new_pw_input.value
                confirm_pw = confirm_pw_input.value

                if not all([current_pw, new_pw, confirm_pw]):
                    ui.notify("Please fill in all password fields", type="negative")
                    return

                if not verify_password(current_pw, user["password_hash"]):
                    ui.notify("Current password is incorrect", type="negative")
                    return

                if new_pw != confirm_pw:
                    ui.notify("New passwords do not match", type="negative")
                    return

                if len(new_pw) < 6:
                    ui.notify("Password must be at least 6 characters", type="negative")
                    return

                new_hash = hash_password(new_pw)
                update_user(user_id, password_hash=new_hash)

                current_pw_input.value = ""
                new_pw_input.value = ""
                confirm_pw_input.value = ""

                ui.notify("Password changed successfully", type="positive")

            ui.button("Change Password", on_click=change_password).classes(
                "bmd-btn-secondary bmd-btn mt-6"
            )

        with ui.card().classes("bmd-card p-6 w-full border-2 border-red-200"):
            ui.label("Danger Zone").classes("text-xl font-semibold text-red-600 mb-2")
            ui.label(
                "Once you delete your account, there is no going back. All your workflows will be permanently deleted."
            ).classes("text-sm text-gray-600 mb-4")

            async def confirm_delete():
                with ui.dialog() as dialog, ui.card().classes("p-6"):
                    ui.label("Delete Account").classes(
                        "text-xl font-bold text-red-600 mb-4"
                    )
                    ui.label(
                        "Are you sure you want to delete your account? This action cannot be undone."
                    ).classes("text-gray-600 mb-4")

                    with ui.column().classes("w-full gap-1 mb-4"):
                        ui.label("Type your email to confirm:").classes(
                            "text-sm font-medium"
                        )
                        confirm_email_input = (
                            ui.input(placeholder=user["email"])
                            .props("outlined")
                            .classes("w-full")
                        )

                    with ui.row().classes("gap-4 justify-end"):
                        ui.button("Cancel", on_click=dialog.close).props("flat")

                        async def do_delete():
                            if confirm_email_input.value != user["email"]:
                                ui.notify("Email doesn't match", type="negative")
                                return

                            delete_user(user_id)
                            app.storage.user.clear()
                            dialog.close()
                            ui.notify("Account deleted", type="info")
                            ui.navigate.to("/login")

                        ui.button("Delete Account", on_click=do_delete).classes(
                            "bmd-btn-danger bmd-btn"
                        )

                dialog.open()

            ui.button("Delete Account", on_click=confirm_delete).classes(
                "bmd-btn-danger bmd-btn"
            ).props("icon=delete")
    create_footer()
