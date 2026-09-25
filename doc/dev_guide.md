# bat-nicegui developer guide

<br>

Welcome to the BMD nice-gui developer guide.

- 🐣 If you are new to the project, please read the
  [BATs Onboarding Guide](bat_onboarding_guide.md).
- 🔨 For detailed instructions on how to add a BAT to the application, please
  refer to the [adding a new BAT documentation](./new_bat_guide.md).

<br>

**To contribute code** to this repository:

1. Request access to the repo if you are a BMD project member, otherwise fork
   the repo.
2. Create a feature branch.
3. Make your changes.
4. Submit a pull request.
5. Please make sure that all CI/CD jobs succeed.

<br>

**✨ Optional prerequisite**: while not mandatory, we warmly recommend using
[uv](https://docs.astral.sh/uv) to manage your local Python virtual
environment. All instructions in this guide assume that you are using `uv`.

<br>
<br>

## Running the project locally and dependency management

### Local deployment

1. Create a copy of the `.env.sample` environment config file and renamed it
   to `.env`.
2. Change/set the required environment variables in your `.env` file.
3. The application can now be run with the following commands, and becomes
   available locally on [localhost:8000](http://localhost:8000).

```sh
# Install dependencies - also creates a .venv automatically if needed.
uv sync

# Start the application - available on http://localhost:8000
uv run --env-file .env -- uvicorn main:fastapi_app --reload --app-dir app
```

### Dependencies management

Dependencies are declared in `pyproject.toml` and pinned in `uv.lock`. Use
[uv](https://docs.astral.sh/uv/) to manage them:

```bash
uv sync             # Install everything (synchronizes venv and lockfile with pyproject.toml).
uv sync --no-dev    # Install runtime dependencies only.
uv sync --upgrade   # Update venv and lockfile to the latest versions of dependencies.
```

Commit both `pyproject.toml` and `uv.lock` whenever dependencies change.

<br>
<br>

## Code checks

The checks listed in this section are also checked via a CICD pipeline.
All commits should therefore pass these checks before they can me merged to
the project's `main` branch.

### Formatting, linting and type checking

This project uses [ruff](https://docs.astral.sh/ruff) for static checking,
and [mypy](https://mypy-lang.org) for type checking.

```bash
uv run ruff check           # Lint check.
uv run ruff format --check  # Format check only (does not reformat files).
uv run ruff format          # Format files.
uv run mypy                 # Type check.
```

### Unit testing

This project uses [pytest](https://docs.pytest.org). Tests live in the
top-level `tests/` directory (outside `app/`, so they stay out of strict
`mypy` checks and the deployed image). Tests run in CI on every push.

```bash
# Run the test suite.
uv run pytest
```

<br>
<br>

## Commits and versioning

This repository uses
[`bitshifted/git-auto-semver@v2`](https://github.com/marketplace/actions/git-automatic-semantic-versioning)
in [`.github/workflows/ci-pipeline.yml`](.github/workflows/ci-pipeline.yml) to
compute semantic versions.

- Pushes to `main` compute the next semantic version, and can create
  tags/releases.
- Pull request runs compute a short commit-hash version for CI validation.

Tags are expected in `v<major>.<minor>.<patch>` format (for example, `v1.4.2`),
and this repository starts from `0.1.0` when no previous tags exist.

### Commit message template

Please follow this template for your commit messages. Fields shown in
`[square brackets]` are optional.

```txt
Prefix[(scope)]: subject line - max 100 characters

[body] - extended description of commit that can stretch over
multiple lines. Max 100 character per line.

[footer] - links to issues with (Closes #, Fixes #, Relates #) and BREAKING CHANGE:
```

### Allowed Commit Prefixes

The following prefixes are allowed:

- **feat**: new feature
- **fix**: bug fix
- **build**: changes that affect the build system or external dependencies.
- **ci**: changes to CI configuration files and scripts.
- **docs**: documentation only changes
- **perf**: code change that improves performance.
- **refactor**: code change that neither fixes a bug nor adds a feature
- **style**: change in code formatting only (no effect on functionality).
- **test**: change in unittest files only.

### Footer

- Reference to Git issue with `Closes/Close`, `Fixes/Fix`, `Related`.
- Location for `BREAKING CHANGE:` keyword. Add this keyword followed by a
  description of what the commit breaks, why it was necessary, and how users
  should port their code to adapt to the new version.

<br>
<br>

## Database schema

Schemas (tables) stored in the application's SQLite database.

### Users Table

| Column          | Type          | Description                                   |
| --------------- | ------------- | --------------------------------------------- |
| `user_id`       | TEXT (PK)     | UUID primary key                              |
| `email`         | TEXT (UNIQUE) | User email                                    |
| `password_hash` | TEXT          | Bcrypt hashed password                        |
| `name`          | TEXT          | User's full name                              |
| `created_at`    | TIMESTAMP     | Account creation time                         |
| `orcid`         | TEXT          | Optional ORCID identifier                     |
| `keycloak_sub`  | TEXT (UNIQUE) | Keycloak subject identifier linked to account |
| `updated_at`    | TIMESTAMP     | Last update time                              |

### Workflows Table

| Column           | Type      | Description                                                    |
| ---------------- | --------- | -------------------------------------------------------------- |
| `workflow_id`    | TEXT (PK) | UUID primary key                                               |
| `user_id`        | TEXT (FK) | Reference to users table                                       |
| `name`           | TEXT      | Workflow name                                                  |
| `description`    | TEXT      | Workflow description                                           |
| `species_name`   | TEXT      | Selected species (scientific name)                             |
| `species_col_id` | TEXT      | Selected Catalogue of Life identifier (nullable)               |
| `ecosystem_type` | TEXT      | Ecosystem type (terrestrial, freshwater)                       |
| `geometry_type`  | TEXT      | rectangle or polygon                                           |
| `geometry_wkt`   | TEXT      | WKT polygon/rectangle                                          |
| `parameters`     | TEXT      | JSON object of exact Argo/YAML workflow parameters              |
| `parameter_metadata` | TEXT   | JSON object of UI/BAT metadata not sent to Argo (nullable)     |
| `status`         | TEXT      | submitted, running, completed, failed                          |
| `results`        | TEXT      | JSON results (when completed)                                  |
| `error_message`  | TEXT      | Error message (when failed)                                    |
| `created_at`     | TIMESTAMP | Submission time                                                |
| `updated_at`     | TIMESTAMP | Last update time                                               |
| `completed_at`   | TIMESTAMP | Completion time                                                |

<br>
<br>

## Project Structure

```sh
bat-nicegui/
├── app/
│   ├── main.py                # Composition root (FastAPI app + NiceGUI mount)
│   ├── api/
│   │   ├── auth.py            # /api/auth/* endpoints
│   │   └── workflows.py       # /api/workflows/* endpoints
│   ├── bats/
│   │   └── terrestrial_sdm.py # /create/terrestrial page
│   ├── pages/                 # Non-BAT application pages
│   │   ├── __init__.py        # register_ui_pages()
│   │   ├── root.py            # / page
│   │   ├── login.py           # /login page
│   │   ├── select_workflow.py # /select-workflow page
│   │   ├── account.py         # /account page
│   │   ├── workflows.py       # /workflows page
│   │   └── results.py         # /results/{id} page
│   ├── ui_common.py           # Shared UI helpers/styles/header/footer/auth check
│   ├── auth_utils.py          # JWT + password helpers
│   ├── workflow_utils.py      # RO-Crate + workflow API helper functions
│   ├── schemas.py             # Pydantic request models
│   ├── config.py              # Environment-backed settings
│   ├── database.py            # SQLite database operations
│   └── templates/
│       ├── terrestrial-sdm/
│       │   ├── workflow.yaml           # Argo workflow template
│       │   └── ro-crate-metadata.json  # RO-Crate metadata template
│       └── freshwater-sdm/
│           ├── workflow.yaml           # Argo workflow template
│           └── ro-crate-metadata.json  # RO-Crate metadata template
├── static/
│   ├── logo.png               # BMD logo
│   └── Invasive_Alien_Species_of_Union_Concern.json  # Updated species list
├── tests/
│   ├── conftest.py            # Puts app/ on sys.path for imports
│   └── test_registry.py       # BAT registry tests
├── Dockerfile           # Docker build instructions
├── docker-compose.yml   # Docker Compose configuration
├── pyproject.toml       # Project metadata and dependencies
├── uv.lock              # Pinned dependency versions (uv)
└── README.md            # This file
```
