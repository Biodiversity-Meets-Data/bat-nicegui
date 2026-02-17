"""Shared NiceGUI UI helpers."""

from typing import Optional

from nicegui import app, ui

from auth_utils import verify_token


def create_footer():
    """Global BMD footer."""
    with ui.footer().classes(
        "w-full justify-center items-center py-3 bg-transparent text-xs text-gray-500",
    ):
        ui.html(
            """
            <span>
                © <a href="https://bmd-project.eu" target="_blank" class="font-medium text-emerald-700 hover:underline">BMD</a> 2025.
                Built with 💚 at
                <a href="https://www.ufz.de" target="_blank" class="font-medium text-emerald-700 hover:underline">Helmholtz‑UFZ</a>
                for biodiversity research.
            </span>
            """,
            sanitize=False,
        )


def apply_bmd_theme():
    """Apply BMD theme styling."""
    ui.add_head_html(
        """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.js"></script>
    <style>
        :root {
            --bmd-green: #2ECC71;
            --bmd-dark-green: #1A9F53;
            --bmd-teal: #17A2B8;
            --bmd-blue: #0077B6;
            --bmd-bg: #F0F9F4;
            --bmd-text: #1A3A2A;
        }

        body {
            font-family: 'Outfit', sans-serif !important;
            min-height: 100vh;
            background: #F0F9F4; /* default for app/dashboard */
        }

        /* ------------------------------------------------------------------
           Public pages (login / signup only)
           ------------------------------------------------------------------ */
        body.public-auth {
            background-image:
                url("https://www.transparenttextures.com/patterns/leaves.png"),
                radial-gradient(circle at 25% 30%, rgba(46,204,113,0.35), transparent 45%),
                radial-gradient(circle at 75% 70%, rgba(23,162,184,0.35), transparent 45%),
                linear-gradient(135deg, #EAF6F0 0%, #DDEFE5 50%, #CFE8E3 100%);
            background-size: 180px 180px, auto, auto, cover;
            background-repeat: repeat;
            background-attachment: fixed;
        }

        .bmd-header {
            background: linear-gradient(135deg, #2ECC71 0%, #17A2B8 50%, #0077B6 100%);
            padding: 1rem 2rem;
            box-shadow: 0 4px 20px rgba(46, 204, 113, 0.3);
        }

        .bmd-card {
            background: white;
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(26, 58, 42, 0.1);
            border: 1px solid rgba(46, 204, 113, 0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }

        .bmd-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 40px rgba(46, 204, 113, 0.15);
        }

        .bmd-btn {
            background: linear-gradient(135deg, #2ECC71 0%, #1A9F53 100%);
            color: white;
            border: none;
            border-radius: 12px;
            padding: 12px 24px;
            font-weight: 600;
            font-family: 'Outfit', sans-serif;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(46, 204, 113, 0.3);
        }

        .bmd-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(46, 204, 113, 0.4);
        }

        .bmd-btn-secondary {
            background: linear-gradient(135deg, #17A2B8 0%, #0077B6 100%);
        }

        .bmd-btn-danger {
            background: linear-gradient(135deg, #E74C3C 0%, #C0392B 100%);
            box-shadow: 0 4px 15px rgba(231, 76, 60, 0.3);
        }

        .bmd-btn-danger:hover {
            box-shadow: 0 6px 20px rgba(231, 76, 60, 0.4);
        }

        .bmd-logo-text {
            font-family: 'Outfit', sans-serif;
            font-weight: 700;
            font-size: 1.8rem;
            background: linear-gradient(135deg, #ffffff 0%, #E8F5E9 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .bmd-subtitle {
            font-family: 'Space Mono', monospace;
            font-size: 0.85rem;
            color: rgba(255, 255, 255, 0.9);
            letter-spacing: 0.5px;
        }

        #map {
            height: 400px;
            width: 100%;
            border-radius: 12px;
            border: 2px solid rgba(46, 204, 113, 0.2);
        }

        .leaflet-draw-toolbar a {
            background-color: #2ECC71 !important;
        }

        .nav-link {
            color: rgba(255, 255, 255, 0.9);
            text-decoration: none;
            font-weight: 500;
            padding: 8px 16px;
            border-radius: 8px;
            transition: all 0.3s ease;
        }

        .nav-link:hover {
            background: rgba(255, 255, 255, 0.15);
            color: white;
        }

        .nav-link.active {
            background: rgba(255, 255, 255, 0.2);
            color: white;
        }

        .required-asterisk {
            color: #E74C3C;
            margin-left: 2px;
        }

        .field-label {
            font-size: 0.875rem;
            font-weight: 500;
            color: #374151;
            margin-bottom: 4px;
        }

        .optional-hint {
            font-size: 0.75rem;
            color: #9CA3AF;
            font-weight: 400;
        }

        /* Ecosystem selection cards */
        .ecosystem-card {
            background: white;
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(26, 58, 42, 0.1);
            border: 2px solid rgba(46, 204, 113, 0.2);
            transition: all 0.4s ease;
            cursor: pointer;
        }

        .ecosystem-card:not(.disabled):hover {
            transform: translateY(-8px);
            box-shadow: 0 16px 48px rgba(46, 204, 113, 0.25);
            background: linear-gradient(135deg, rgba(46, 204, 113, 0.05) 0%, rgba(23, 162, 184, 0.05) 100%);
            border-color: rgba(46, 204, 113, 0.4);
        }

        .ecosystem-card.disabled {
            opacity: 0.5;
            cursor: not-allowed;
            background: #f5f5f5;
        }

        .ecosystem-icon {
            font-size: 6rem;
            background: linear-gradient(135deg, #2ECC71 0%, #17A2B8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .ecosystem-card.disabled .ecosystem-icon {
            background: #9CA3AF;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .ecosystem-action-btn {
            padding: 8px 16px;
            min-height: 38px;
            font-size: 0.875rem;
        }

        .species-pill {
            display: inline-block;
            margin-left: 6px;
            padding: 2px 8px;
            border-radius: 999px;
            background: rgba(46, 204, 113, 0.15);
            color: #1A9F53;
            font-size: 0.7rem;
            font-weight: 600;
            vertical-align: middle;
        }

        .time-period-slider .q-slider__marker-label {
            font-size: 0.7rem;
            max-width: 70px;
            white-space: normal;
            line-height: 1.1;
            text-align: center;
        }
    </style>
    """
    )


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


def create_header(current_page: str = ""):
    """Create the BMD header with navigation."""
    user_name = app.storage.user.get("user_name", "User")

    with ui.header().classes("bmd-header items-center justify-between"):
        with ui.row().classes("items-center gap-3"):
            with ui.column().classes("gap-0 cursor-pointer").on(
                "click", lambda: ui.navigate.to("/workflows")
            ):
                ui.label("BMD").classes("bmd-logo-text")
                ui.label("Biodiversity Meets Data").classes("bmd-subtitle")

        with ui.row().classes("gap-3 items-center"):
            ui.link("Workflows", "/workflows").classes(
                f'nav-link {"active" if current_page == "workflows" else ""}'
            )
            ui.button(
                "+ New Workflow", on_click=lambda: ui.navigate.to("/select-workflow")
            ).props("unelevated rounded color=white text-color=primary").classes(
                "font-semibold"
            )

            with ui.button(icon="account_circle").props("flat round color=white"):
                with ui.menu().classes("min-w-48"):
                    with ui.row().classes("px-4 py-3 border-b border-gray-100"):
                        with ui.column().classes("gap-0"):
                            ui.label(user_name).classes("font-semibold text-gray-800")
                            ui.label("Logged in").classes("text-xs text-gray-500")
                    ui.menu_item(
                        "Account Settings", on_click=lambda: ui.navigate.to("/account")
                    ).classes("py-2")
                    ui.separator()
                    ui.menu_item("Logout", on_click=lambda: do_logout()).classes(
                        "py-2 text-red-600"
                    )


async def do_logout():
    app.storage.user.clear()
    ui.navigate.to("/login")


def check_auth() -> Optional[str]:
    """Check if user is authenticated."""
    token = app.storage.user.get("token")
    if not token:
        return None
    return verify_token(token)
