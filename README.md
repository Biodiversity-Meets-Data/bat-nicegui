# 🌿 BMD - Biodiversity Meets Data

A modern web application for biodiversity analysis workflows, built with NiceGUI and FastAPI.

![BMD Logo](static/logo.png)

## Features

- **User Authentication**: Secure signup/login with JWT tokens and SQLite backend
- **Interactive Map**: Draw bounding boxes and polygons on a Europe-restricted Leaflet map
- **Workflow Submission**: Submit analysis workflows with configurable parameters
- **Workflow Tracking**: View all submitted workflows and their status
- **Webhook Integration**: Receive results from Argo Workflow via webhooks
- **Themed UI**: Beautiful green-to-teal gradient theme matching the BMD brand

## Tech Stack

- **Frontend**: NiceGUI with Tailwind CSS
- **Backend**: FastAPI (Python)
- **Database**: SQLite
- **Authentication**: JWT tokens with bcrypt password hashing
- **Map**: Leaflet.js with Leaflet.Draw plugin
- **Container**: Docker

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
| `species_group` | TEXT | Target species group |
| `date_range_start` | TEXT | Analysis start date |
| `date_range_end` | TEXT | Analysis end date |
| `geometry_type` | TEXT | rectangle or polygon |
| `geometry_coords` | TEXT | JSON array of coordinates |
| `parameters` | TEXT | JSON object of parameters |
| `status` | TEXT | submitted, running, completed, failed |
| `results` | TEXT | JSON results (when completed) |
| `error_message` | TEXT | Error message (when failed) |
| `created_at` | TIMESTAMP | Submission time |
| `updated_at` | TIMESTAMP | Last update time |
| `completed_at` | TIMESTAMP | Completion time |

## Argo Workflow Integration

To integrate with your Argo Workflow server:

1. Update the `ARGO_WORKFLOW_URL` environment variable
2. Modify the `api_submit_workflow` function in `main.py` to make actual POST requests:

```python
# Replace simulate_workflow_processing with actual Argo API call
async def submit_to_argo(workflow_id: str, workflow_data: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{ARGO_WORKFLOW_URL}/api/v1/workflows/{ARGO_NAMESPACE}",
            json={
                "workflow": {
                    "metadata": {"name": workflow_id},
                    "spec": {
                        # Your Argo workflow spec here
                        "arguments": workflow_data
                    }
                }
            }
        )
        return response.json()
```

3. Configure your Argo Workflow template to call the webhook on completion

## Project Structure

```
bmd-app/
├── app/
│   ├── main.py          # Main application (NiceGUI + FastAPI)
│   └── database.py      # SQLite database operations
├── static/
│   └── logo.png         # BMD logo
├── Dockerfile           # Docker build instructions
├── docker-compose.yml   # Docker Compose configuration
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variables template
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

1. Add new API endpoints in `main.py`
2. Update database schema in `database.py`
3. Add NiceGUI pages for new UI features

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
