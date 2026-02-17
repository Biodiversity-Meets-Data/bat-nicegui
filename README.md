# 🌿 BMD - Biodiversity Meets Data

A modern web application for biodiversity analysis workflows, built with NiceGUI and FastAPI.

![BMD Logo](static/logo.png)

## Features

- **User Authentication**: Secure signup/login with JWT tokens and SQLite backend
- **Interactive Map**: Draw bounding boxes and polygons on a Europe-restricted Leaflet map
- **Workflow Submission**: Submit analysis workflows with configurable parameters
- **Workflow Tracking**: View all submitted workflows and their status
- **Ecosystem Types**: Tag workflows by ecosystem (terrestrial/freshwater)
- **RO-Crate Submission**: Generate `workflow.yaml` and `rocrate.json` from templates and upload as a ZIP
- **Webhook Integration**: Receive results from Argo Workflow via webhooks
- **Themed UI**: Beautiful green-to-teal gradient theme matching the BMD brand

## Tech Stack

- **Frontend**: NiceGUI with Tailwind CSS
- **Backend**: FastAPI (Python)
- **Database**: SQLite
- **Authentication**: JWT tokens with bcrypt password hashing
- **Map**: Leaflet.js with Leaflet.Draw plugin
- **Container**: Docker

## Request Flow Diagram

```
Browser (NiceGUI UI)
  | 1) POST /api/auth/login
  v
bmd-bat-app (FastAPI + NiceGUI)
  | 2) POST /api/workflows/submit
  |    - builds RO-Crate ZIP
  |    - forwards to workflow API
  v
workflow-api (external service)
  | 3) POST /api/workflows/webhook/{workflow_id} (webhook callback)
  v
bmd-bat-app (updates SQLite, UI refresh)
```

## Quick Start

### Using Docker Compose (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd bat-nicegui

# Copy environment configuration
cp .env.example .env

# Edit .env and set a secure SECRET_KEY
nano .env

# Build and run
docker-compose up --build

# Access the application at http://localhost:8080
```

### Manual Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export SECRET_KEY="your-secret-key"
export DATABASE_PATH="./data/bmd.db"
export WORKFLOW_WAIT_TIME=20

# Run the application
cd app
python main.py
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | JWT signing key (CHANGE IN PRODUCTION) | `bmd-secret-key-...` |
| `DATABASE_PATH` | SQLite database file path | `/app/data/bmd.db` |
| `WORKFLOW_WAIT_TIME` | Simulated workflow processing time (seconds) | `20` |
| `ARGO_WORKFLOW_URL` | Argo Workflow server URL | `http://argo-workflow-server:2746` |
| `ARGO_WORKFLOW_NAMESPACE` | Argo namespace | `argo` |
| `WORKFLOW_API_URL` | External workflow submission endpoint | `http://localhost:1245/api/v1/workflows` |
| `WORKFLOW_API_KEY` | API key for workflow API (sent as Bearer token) | (empty) |
| `WORKFLOW_WEBHOOK_URL_TEMPLATE` | Webhook URL template (supports `{workflow_id}`) | `http://localhost:8080/api/workflows/webhook/{workflow_id}` |
| `WORKFLOW_DRY_RUN` | Validate only (true/false) | `false` |
| `WORKFLOW_FORCE` | Force re-execution (true/false) | `false` |

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/signup` | Create new user account |
| POST | `/api/auth/login` | Login and get JWT token |

### Workflows

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/workflows/submit` | Submit new analysis workflow |
| GET | `/api/workflows` | Get all workflows for authenticated user |
| POST | `/api/workflows/webhook/{workflow_id}` | Webhook for workflow completion |

### Workflow Webhook Payload

When your Argo Workflow completes, call the webhook with:

```json
POST /api/workflows/webhook/{workflow_id}
{
  "workflow_id": "uuid-string",
  "status": "completed",  // or "failed"
  "results": {
    "species_count": 42,
    "observation_count": 1337,
    "biodiversity_index": 0.78
  },
  "error_message": null  // or error string if failed
}
```

## Database Schema

### Users Table

| Column | Type | Description |
|--------|------|-------------|
| `user_id` | TEXT (PK) | UUID primary key |
| `email` | TEXT (UNIQUE) | User email |
| `password_hash` | TEXT | Bcrypt hashed password |
| `name` | TEXT | User's full name |
| `created_at` | TIMESTAMP | Account creation time |
| `updated_at` | TIMESTAMP | Last update time |

### Workflows Table

| Column | Type | Description |
|--------|------|-------------|
| `workflow_id` | TEXT (PK) | UUID primary key |
| `user_id` | TEXT (FK) | Reference to users table |
| `name` | TEXT | Workflow name |
| `description` | TEXT | Workflow description |
| `species_name` | TEXT | Selected species (scientific name) |
| `ecosystem_type` | TEXT | Ecosystem type (terrestrial, freshwater) |
| `geometry_type` | TEXT | rectangle or polygon |
| `geometry_wkt` | TEXT | WKT polygon/rectangle |
| `parameters` | TEXT | JSON object of parameters (time_period, directive_types, etc.) |
| `status` | TEXT | submitted, running, completed, failed |
| `results` | TEXT | JSON results (when completed) |
| `error_message` | TEXT | Error message (when failed) |
| `created_at` | TIMESTAMP | Submission time |
| `updated_at` | TIMESTAMP | Last update time |
| `completed_at` | TIMESTAMP | Completion time |

## External Workflow Submission

On submission, the backend reads:
- `app/templates/terrestrial-sdm/workflow.yaml`
- `app/templates/terrestrial-sdm/ro-crate-metadata.json`

These files are zipped into an RO-Crate and POSTed to `WORKFLOW_API_URL`. The external API returns
the `workflow_id`, which is stored in the local database. Webhook delivery uses
`WORKFLOW_WEBHOOK_URL_TEMPLATE` (supports `{workflow_id}`).

## Project Structure

```
bat-nicegui/
├── app/
│   ├── main.py                # Composition root (FastAPI app + NiceGUI mount)
│   ├── api/
│   │   ├── auth.py            # /api/auth/* endpoints
│   │   └── workflows.py       # /api/workflows/* endpoints
│   ├── bats/
│   │   └── terrestrial_sdm.py # /create/terrestrial page
│   ├── page_login.py
│   ├── page_signup.py
│   ├── page_select_workflow.py
│   ├── page_account.py
│   ├── page_workflows.py
│   ├── page_results.py
│   ├── page_root.py
│   ├── ui_common.py           # Shared UI helpers/styles/header/footer/auth check
│   ├── auth_utils.py          # JWT + password helpers
│   ├── workflow_utils.py      # RO-Crate + workflow API helper functions
│   ├── schemas.py             # Pydantic request models
│   ├── config.py              # Environment-backed settings
│   ├── database.py            # SQLite database operations
│   └── templates/
│       └── terrestrial-sdm/
│           ├── workflow.yaml           # Argo workflow template
│           └── ro-crate-metadata.json  # RO-Crate metadata template
├── static/
│   ├── logo.png         # BMD logo
│   └── eu-ias-directive.json  # EU IAS directive data
├── Dockerfile           # Docker build instructions
├── docker-compose.yml   # Docker Compose configuration
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

## Development

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/
```

### Adding New Features

1. Add/extend API endpoints in `app/api/auth.py` or `app/api/workflows.py`
2. Update database schema or queries in `app/database.py`
3. Add non-create UI pages as top-level `app/page_*.py` modules
4. Add/create workflow UI pages under `app/bats/` (for terrestrial SDM use `app/bats/terrestrial_sdm.py`)

## Security Notes

⚠️ **For Production Deployment:**

1. Change the `SECRET_KEY` to a secure random string
2. Use HTTPS (configure nginx reverse proxy)
3. Set up proper CORS if needed
4. Consider using PostgreSQL instead of SQLite for scalability
5. Add rate limiting for API endpoints
6. Enable proper logging and monitoring

## License

MIT License - See LICENSE file for details

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

Built with 💚 for biodiversity research
