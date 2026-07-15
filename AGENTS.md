# AGENTS.md

Guidance for AI coding agents and contributors working in this repository. For
architecture, deployment, API, and database details, see [README.md](README.md).

## What this is

A NiceGUI + FastAPI web app that is the entrypoint for BMD Biodiversity Analysis
Tools (BATs). Users authenticate, draw an analysis area on a map, configure a
workflow, and submit it to an external workflow API. All application code lives
under `app/`.

## Setup & commands

This project uses [uv](https://docs.astral.sh/uv). The package itself is not
installed (it is a deployable app, not a library).

```bash
uv sync                     # Install dependencies (creates .venv if needed).

# Run the app locally (serves on http://localhost:8000):
export DATABASE_PATH="./data/bmd.db"
uv run -- uvicorn main:fastapi_app --reload --app-dir app
```

## Checks that must pass

CI runs these and so should you, before every commit. All must be clean.

```bash
uv run ruff check           # Lint.
uv run ruff format --check  # Formatting (run `uv run ruff format` to fix).
uv run mypy                 # Type check.
```

`mypy` is configured in `pyproject.toml` as `strict = true` over `app/`. New
code must type-check under strict mode.

## Code conventions

- **Modern type hints.** Use `X | None`, `list[str]`, `dict[str, Any]` — not
  `Optional`, `List`, `Dict`. Annotate every function (including `-> None`); all
  code must pass `mypy --strict`.
- **Dataclasses use `@dataclass(frozen=True, slots=True)`.** This is the default
  for value objects: `frozen` makes them immutable, `slots` saves memory and
  turns attribute typos into `AttributeError` instead of silent bugs. Add
  `kw_only=True` when a class has several fields so call sites can't transpose
  positional arguments. See `MapGeometry`, `Bat`, `WorkflowPayload`.
- **Prefer NiceGUI APIs over raw JavaScript.** To manipulate existing elements
  (e.g. the `<body>`), use `ui.query(...)` rather than `ui.run_javascript(...)`.
  Reserve `run_javascript` for genuinely client-only logic (e.g. the Leaflet
  map in `bats/map_widget.py`).
- **Separate validation from presentation.** Input validation raises
  `WorkflowValidationError` with a user-facing message; the page's event handler
  catches it and calls `ui.notify`. Keep shared/domain logic independent of the
  `ui` layer.
- **Docstrings.** When possible, avoid naming literal methods/symbols in
  docstrings and comments; they go stale on rename.

## Layout of `app/`

Non-obvious structure (the full tree is in the README):

- `bats/registry.py` — single source of truth for BAT definitions (`Bat`,
  `EcosystemCategory`, `BAT_REGISTRY`). Register new BATs here.
- `bats/workflow.py` — the workflow domain layer: `WorkflowPayload`, the
  `BatSpecificParameters` base for per-BAT parameters, input validation
  (`build_workflow_payload`), and submission (`submit_workflow`). Raises
  `WorkflowValidationError`.
- `bats/map_widget.py` — shared Leaflet map widget and reading the drawn geometry
  (`MapGeometry`, `add_map_widget`, `init_map`, `read_map_geometry`).
- `bats/base_page.py` — `BasePage`, the abstract base every BAT page subclasses.
  Owns the shared form (name/description/area), the submit flow, and route
  registration; subclasses supply only the BAT-specific parameters.
- `bats/<name>.py` — one page module per BAT (e.g. `terrestrial_sdm.py`,
  `terrestrial_captain.py`). Each subclasses `BasePage` and defines a
  `BatSpecificParameters` subclass for its typed parameters.
- `page_*.py` — top-level, non-BAT pages (login, signup, account, …).
- `ui_common.py` — shared header/footer/theme/auth helpers.
- `ui_widgets.py` — reusable input-widget builders (`required_label`,
  `optional_label`, `drop_down_menu`).
- `api/` — FastAPI endpoints; `schemas.py` — Pydantic request models;
  `database.py` — SQLite access; `config.py` — env-backed settings.

Dependency direction inside `bats/` is one-way: `workflow.py` and `map_widget.py`
are the base layers, `base_page.py` builds on both, and each BAT page builds on
`base_page.py`. Never import a BAT page from a shared module.

## Adding a new BAT

BAT pages subclass a shared base (`BasePage`, in `bats/base_page.py`) that owns
the common form (name, description, analysis area), the validation/submit flow,
and route registration. A new BAT only supplies its own parameters. The easiest
path is to copy an existing BAT page and adapt it:

1. Register the BAT in `bats/registry.py` (`BAT_REGISTRY`).
2. In `bats/<name>.py`, define a `BatSpecificParameters` subclass — a
   `@dataclass(frozen=True, slots=True, kw_only=True)` holding the BAT's typed
   parameters — that validates them and serializes them to the API `parameters`
   dict.
3. In the same module, define a `BasePage` subclass: set its `BAT` class
   attribute and implement the abstract methods (build the BAT-specific input
   widgets; collect them into the arguments object). Override the species hooks
   only if the BAT has a species input.
4. Call the subclass's `register()` at the bottom of the module. `pages.py`
   imports every BAT module listed in the registry, which triggers registration.
5. Read the
   [BATs Onboarding Guide](https://github.com/Biodiversity-Meets-Data/infrastructure-docs/blob/main/docs/BAT_onboarding_guide.md).

## Commits

Use Conventional-Commit prefixes (`feat:`, `fix:`, `refactor:`, `docs:`,
`chore:`, `ci:`, `test:`, …); CI derives semantic versions from them. See the
"Allowed Commit Prefixes" table in the README.
