"""Shared NiceGUI UI helpers."""

import enum

from nicegui import app, context, ui

from auth_utils import verify_token
from database import DatabaseError, create_feedback


class PageHeader(enum.Enum):
    NONE = enum.auto()
    BASE = enum.auto()
    WORKFLOW_PAGE = enum.auto()


def add_development_banner() -> None:
    """Adds the platform maturity notice above authenticated pages."""
    with ui.element("div").classes(
        "w-full bg-red-700 px-4 py-2 text-center text-sm font-semibold text-white"
    ):
        ui.label(
            "Early development phase: persistence is not guaranteed and changes are expected."
        )


def add_header(header: PageHeader = PageHeader.BASE) -> None:
    """Adds the BMD header with navigation tools to the page.

    Arguments:
    * header: type of header to create. In headers for the workflow page, the
        "Workflows" button is displayed as being pressed, indicating that the
        Workflow page is the currently active page.
    """
    user_name = app.storage.user.get("user_name", "User")

    with ui.header().classes("bmd-header items-center justify-between"):
        with ui.row().classes("items-center gap-3"):
            with (
                ui.column()
                .classes("gap-0 cursor-pointer")
                .on("click", lambda: ui.navigate.to("/workflows"))
            ):
                ui.image("/static/bmd_small.svg").props('alt="BMD logo"').classes(
                    "bmd-header-logo w-24 h-auto"
                )

        with ui.row().classes("gap-3 items-center"):
            ui.link("Workflows", "/workflows").classes(
                "nav-link" + (" active" if header is PageHeader.WORKFLOW_PAGE else "")
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


def add_footer() -> None:
    """Adds a footer to the page. Currently this footer is used globally
    for all pages.
    """

    with ui.footer().classes(
        "bmd-footer fixed bottom-0 left-0 z-[900] w-full justify-center items-center "
        "py-3 bg-white/90 backdrop-blur text-xs text-gray-500",
    ):
        with ui.element("div").classes("relative w-full"):
            with ui.element("div").classes("feedback-footer-control absolute top-1/2"):
                add_feedback_widget()
            with ui.row().classes("items-center justify-center gap-3 flex-wrap"):
                ui.html(
                    '<img src="/static/eu.png" alt="European Union logo" '
                    'style="display:block;width:78px;height:69px;object-fit:contain;" />',
                    sanitize=False,
                )
                ui.html(
                    """
                    <span class="text-[#0F2F2A]">
                        © <a href="https://bmd-project.eu" target="_blank" class="font-medium text-[#0F2F2A] hover:underline">BMD</a> 2026.
                        Built with 💚 for biodiversity research.
                    </span>
                    """,
                    sanitize=False,
                )


def add_feedback_widget() -> None:
    """Add the authenticated user's fixed feedback control."""
    user_id = app.storage.user.get("user_id")
    if not isinstance(user_id, str) or not user_id:
        return

    page = context.client.request.url.path

    with (
        ui.element("div")
        .classes("relative z-[2000]")
        .style("z-index: 2000; pointer-events: auto;")
    ):
        feedback_open = False
        with ui.card().classes("feedback-card feedback-popup p-5 gap-3") as popup:
            ui.label("Send feedback").classes("text-lg font-semibold")
            ui.label(
                "Tell us what worked well or what we can improve on this page."
            ).classes("text-sm text-gray-500")
            feedback_input = (
                ui.textarea(
                    label="Your feedback for this page",
                    placeholder="Write your feedback here...",
                )
                .props("outlined maxlength=2000 counter")
                .classes("w-full")
            )

            def submit_feedback() -> None:
                nonlocal feedback_open
                try:
                    create_feedback(
                        user_id=user_id,
                        page=page,
                        message=str(feedback_input.value or ""),
                    )
                except ValueError as exc:
                    ui.notify(str(exc), type="negative")
                except DatabaseError:
                    ui.notify(
                        "Feedback could not be sent. Please try again.",
                        type="negative",
                    )
                else:
                    feedback_input.set_value("")
                    feedback_open = False
                    popup.set_visibility(False)
                    ui.notify("Feedback sent", type="positive")

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Send", on_click=submit_feedback).classes("bmd-btn")

        popup.set_visibility(False)

        def toggle_feedback() -> None:
            nonlocal feedback_open
            feedback_open = not feedback_open
            popup.set_visibility(feedback_open)

        with ui.row().classes("w-full justify-center"):
            ui.chip("Feedback", icon="chat_bubble_outline", color=None).classes(
                "feedback-launcher cursor-pointer px-3 py-2 sm:px-4 text-sm sm:text-base"
            ).style(
                "background: linear-gradient(135deg, #20A683 0%, #1A8F6F 100%) "
                "!important; color: #FFFFFF !important;"
            ).on_click(toggle_feedback)


def apply_bmd_theme(
    header: PageHeader = PageHeader.BASE, public_auth: bool = False
) -> None:
    """Apply BMD theme styling.

    Arguments
    * header: type of header to be added to the page.
    * public_auth: if True, the styling for public (non-authenticated) pages
      is used.
    """

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
            --bmd-forest: #0F2F2A;
            --bmd-jade: #20A683;
            --bmd-jade-dark: #1A8F6F;
            --bmd-teal: #0D969C;
            --bmd-bg: #F3F7F5;
            --bmd-surface: #FFFFFF;
            --bmd-border: #DCE7E3;
            --bmd-text: #0F2F2A;
            --bmd-muted: #60716D;
            --bmd-danger: #B54747;
        }

        body {
            font-family: 'Outfit', sans-serif !important;
            min-height: 100vh;
            background:
                radial-gradient(circle at 8% 12%, rgba(32, 166, 131, 0.14), transparent 38%),
                radial-gradient(circle at 88% 84%, rgba(13, 150, 156, 0.12), transparent 42%),
                linear-gradient(135deg, #F6FBF8 0%, #EAF6F0 55%, #E4F1F3 100%);
            background-attachment: fixed;
            color: var(--bmd-text);
            -webkit-font-smoothing: antialiased;
        }

        #app {
            min-height: 100vh;
            padding-bottom: 5.5rem;
        }

        .bmd-header {
            background: linear-gradient(135deg, #2ECC71 0%, #17A2B8 50%, #0077B6 100%);
            padding: 0.7rem clamp(1rem, 4vw, 3rem);
            min-height: 4.25rem;
            box-shadow: 0 4px 20px rgba(32, 166, 131, 0.26);
        }

        .bmd-card {
            background: var(--bmd-surface);
            border-radius: 14px;
            box-shadow: 0 8px 28px rgba(15, 47, 42, 0.06);
            border: 1px solid var(--bmd-border);
            transition: box-shadow 0.2s ease, border-color 0.2s ease;
        }

        .bmd-card:hover {
            box-shadow: 0 12px 32px rgba(15, 47, 42, 0.09);
        }

        .bmd-btn {
            background: var(--bmd-surface) !important;
            color: var(--bmd-forest) !important;
            border: 1px solid var(--bmd-border);
            border-radius: 10px;
            padding: 10px 20px;
            font-weight: 600;
            font-family: 'Outfit', sans-serif;
            cursor: pointer;
            transition: transform 0.2s ease, box-shadow 0.2s ease,
                        border-color 0.2s ease, background-color 0.2s ease;
            box-shadow: 0 3px 10px rgba(15, 47, 42, 0.1);
        }

        .bmd-btn:hover {
            transform: translateY(-2px);
            border-color: rgba(32, 166, 131, 0.55);
            box-shadow: 0 7px 18px rgba(15, 47, 42, 0.14);
        }

        .bmd-btn:focus-visible,
        .nav-link:focus-visible,
        .feedback-launcher:focus-visible {
            outline: 3px solid rgba(32, 166, 131, 0.35);
            outline-offset: 2px;
        }

        .bmd-btn-primary {
            background: var(--bmd-jade) !important;
            color: white !important;
            border-color: var(--bmd-jade) !important;
            box-shadow: 0 6px 16px rgba(32, 166, 131, 0.24);
        }

        .bmd-btn-primary:hover {
            background: var(--bmd-jade-dark) !important;
            border-color: var(--bmd-jade-dark) !important;
            box-shadow: 0 9px 22px rgba(32, 166, 131, 0.3);
        }

        .bmd-btn-secondary {
            color: var(--bmd-teal) !important;
            border-color: rgba(13, 150, 156, 0.3);
        }

        .bmd-btn-danger {
            background: var(--bmd-danger) !important;
            color: white !important;
            border-color: var(--bmd-danger) !important;
            box-shadow: 0 4px 14px rgba(181, 71, 71, 0.22);
        }

        .bmd-btn-danger:hover {
            box-shadow: 0 7px 18px rgba(181, 71, 71, 0.3);
        }

        .feedback-launcher.q-chip {
            background-color: #1A8F6F !important;
            background-image: linear-gradient(135deg, #20A683 0%, #1A8F6F 100%) !important;
            color: #FFFFFF !important;
            border: 1px solid rgba(255, 255, 255, 0.24);
            box-shadow: 0 10px 30px rgba(26, 58, 42, 0.2),
                        0 2px 8px rgba(32, 166, 131, 0.2);
            font-weight: 600;
            letter-spacing: 0.01em;
            transition: transform 0.2s ease, box-shadow 0.2s ease,
                        border-color 0.2s ease;
        }

        .feedback-launcher.q-chip:hover {
            background-color: #1A8F6F !important;
            background-image: linear-gradient(135deg, #28B792 0%, #167A5E 100%) !important;
            border-color: rgba(255, 255, 255, 0.42);
            box-shadow: 0 14px 34px rgba(26, 58, 42, 0.24),
                        0 4px 12px rgba(32, 166, 131, 0.3);
            transform: translateY(-2px);
        }

        .feedback-launcher.q-chip .q-icon,
        .feedback-launcher.q-chip .q-chip__content {
            color: #FFFFFF !important;
        }

        .feedback-card {
            background: rgba(255, 255, 255, 0.98) !important;
            border: 1px solid var(--bmd-border);
            border-radius: 14px;
            box-shadow: 0 18px 50px rgba(15, 47, 42, 0.18);
        }

        .feedback-footer-control {
            left: 25px;
            width: min(320px, calc(100vw - 50px));
            transform: translateY(-50%);
        }

        .feedback-popup {
            position: absolute;
            left: 0;
            bottom: calc(100% + 0.75rem);
            width: 100%;
            max-width: calc(100vw - 50px);
            margin: 0 !important;
            box-sizing: border-box;
            z-index: 2001;
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

        .bmd-header-logo {
            filter: brightness(0) invert(1);
        }

        .q-field--outlined .q-field__control:before {
            border-color: var(--bmd-border);
        }

        .q-field--outlined:hover .q-field__control:before,
        .q-field--outlined.q-field--focused .q-field__control:after {
            border-color: var(--bmd-jade);
        }

        .q-field__label,
        .field-label {
            color: var(--bmd-forest) !important;
        }

        .required-asterisk {
            color: var(--bmd-danger);
        }

        .bmd-footer {
            border-top: 1px solid var(--bmd-border);
        }

        #map {
            height: 400px;
            width: 100%;
            border-radius: 12px;
            border: 2px solid rgba(32, 166, 131, 0.2);
        }

        .leaflet-draw-toolbar a {
            background-color: var(--bmd-jade) !important;
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
            background: rgba(32, 166, 131, 0.22);
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

        /* Compact BAT cards inside category expansions */
        .bat-card {
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 16px rgba(26, 58, 42, 0.08);
            border: 1px solid rgba(32, 166, 131, 0.15);
            transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
            cursor: pointer;
            width: 220px;
            height: 210px;
        }

        .ecosystem-tab {
            position: relative;
            min-height: 64px;
            min-width: 160px;
            padding: 10px 18px;
            border-radius: 12px;
            box-sizing: border-box;
            overflow: hidden;
            background-position: center;
            background-size: cover;
            background-repeat: no-repeat;
            color: white !important;
            text-shadow: 0 1px 3px rgba(0, 0, 0, 0.75);
            opacity: 0.58;
            filter: grayscale(0.7);
            transition: opacity 0.2s ease, filter 0.2s ease, box-shadow 0.2s ease;
        }

        .ecosystem-tab.q-tab--active {
            opacity: 1;
            filter: grayscale(0);
            box-shadow: 0 4px 14px rgba(26, 58, 42, 0.25);
        }

        /* Clamp the description to 2 lines so a long one can't grow the card. */
        .bat-card-desc {
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .bat-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 10px 28px rgba(32, 166, 131, 0.18);
            border-color: rgba(32, 166, 131, 0.4);
        }

        .bat-card-icon {
            font-size: 2.5rem;
            background: linear-gradient(135deg, #20A683 0%, #0D969C 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .species-pill {
            display: inline-block;
            margin-left: 6px;
            padding: 2px 8px;
            border-radius: 999px;
            background: rgba(32, 166, 131, 0.15);
            color: #1A8F6F;
            font-size: 0.7rem;
            font-weight: 600;
            vertical-align: middle;
        }

        .species-pill--ias-union-concern {
            background: rgba(220, 38, 38, 0.14);
            color: #b91c1c;
        }

        .species-pill--habitats-annex-ii {
            background: rgba(37, 99, 235, 0.16);
            color: #1d4ed8;
        }

        .species-pill--habitats-annex-iv {
            background: rgba(37, 99, 235, 0.28);
            color: #1e40af;
        }

        .species-pill--habitats-annex-v {
            background: rgba(37, 99, 235, 0.42);
            color: #1e3a8a;
        }

        .species-pill--habitats-characteristic-annex-i {
            background: rgba(37, 99, 235, 0.10);
            color: #2563eb;
        }

        .species-pill--birds-annex-i {
            background: rgba(147, 51, 234, 0.16);
            color: #7e22ce;
        }

        .species-pill--birds-annex-ii {
            background: rgba(147, 51, 234, 0.28);
            color: #6b21a8;
        }

        .species-pill--birds-annex-iii {
            background: rgba(147, 51, 234, 0.42);
            color: #581c87;
        }

        .time-period-slider .q-slider__marker-label {
            font-size: 0.7rem;
            max-width: 70px;
            white-space: normal;
            line-height: 1.1;
            text-align: center;
        }

        @media (max-width: 640px) {
            .bmd-header {
                padding-inline: 1rem;
            }

            .bmd-header .nav-link {
                padding-inline: 8px;
                font-size: 0.875rem;
            }

            .bmd-header .q-btn {
                min-width: 0;
            }

            .ecosystem-tab {
                min-width: 0;
                flex: 1 1 30%;
                padding-inline: 8px;
            }

            .feedback-footer-control {
                left: 25px;
                width: calc(100vw - 50px);
            }
        }

        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                scroll-behavior: auto !important;
                transition-duration: 0.01ms !important;
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
            }
        }
    </style>
    """
    )

    # Add the decorative background used only on non-authenticated pages
    # such as the login page.
    if public_auth:
        ui.add_head_html(
            """
            <style>
                body {
                    background-image:
                        url("https://www.transparenttextures.com/patterns/leaves.png"),
                        radial-gradient(circle at 25% 30%, rgba(46,204,113,0.45), transparent 45%),
                        radial-gradient(circle at 75% 70%, rgba(23,162,184,0.38), transparent 48%),
                        linear-gradient(135deg, #EAF6F0 0%, #DDEFE5 48%, #CFE8E3 100%);
                    background-size: 180px 180px, auto, auto, cover;
                    background-repeat: repeat;
                    background-attachment: fixed;
                }
            </style>
            """
        )

    # Keep the maturity notice visible across both public and authenticated pages.
    add_development_banner()

    # Add a header to the page, if it has one.
    if header is not PageHeader.NONE:
        add_header(header=header)

    # Add a footer to the page, including the authenticated feedback control.
    add_footer()


async def do_logout() -> None:
    """Logout from the application."""
    ui.navigate.to("/api/auth/logout")


def check_auth() -> str | None:
    """Check if user is authenticated."""
    token = app.storage.user.get("token")
    if not token:
        return None
    return verify_token(token)
