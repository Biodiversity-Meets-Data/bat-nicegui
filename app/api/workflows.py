"""Workflow API routes."""

from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from starlette.background import BackgroundTask

from auth_utils import optional_security, security, verify_token
from config import (
    WORKFLOW_API_AUTH_HEADER,
    WORKFLOW_API_URL,
    WORKFLOW_DRY_RUN,
    WORKFLOW_FORCE,
    WORKFLOW_WEBHOOK_URL_TEMPLATE,
)
from database import (
    create_workflow,
    delete_workflow,
    get_user_workflows,
    get_workflow_by_id,
    update_workflow_status,
)
from schemas import WorkflowSubmit, WorkflowWebhook
from workflow_utils import build_rocrate_zip, build_workflow_api_headers

router = APIRouter()


@router.post("/api/workflows/submit")
async def api_submit_workflow(
    workflow: WorkflowSubmit,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user_id = verify_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    parameters = workflow.parameters or {}
    time_period = parameters.get("time_period", "")
    directive_types = parameters.get("directive_types", [])
    if isinstance(directive_types, list):
        directive_types = ";".join([str(value) for value in directive_types])
    else:
        directive_types = str(directive_types)

    rocrate_context = {
        "workflow_name": workflow.name,
        "description": workflow.description or "",
        "species_name": workflow.species_name,
        "ecosystem_type": workflow.ecosystem_type,
        "geometry_type": workflow.geometry_type,
        "geometry_wkt": workflow.geometry_wkt,
        "time_period": time_period,
        "directive_types": directive_types,
    }
    rocrate_zip = build_rocrate_zip(rocrate_context)

    data = {}
    if WORKFLOW_WEBHOOK_URL_TEMPLATE:
        data["webhook_url"] = WORKFLOW_WEBHOOK_URL_TEMPLATE
    data["dry_run"] = str(WORKFLOW_DRY_RUN).lower()
    data["force"] = str(WORKFLOW_FORCE).lower()
    data["param-target_species"] = workflow.species_name
    data["param-climate_periods"] = time_period
    data["param-aoi_wkt"] = workflow.geometry_wkt

    headers = build_workflow_api_headers()
    safe_headers = dict(headers)
    if WORKFLOW_API_AUTH_HEADER in safe_headers:
        safe_headers[WORKFLOW_API_AUTH_HEADER] = "***"

    print("Submitting workflow to API")
    print(f"URL: {WORKFLOW_API_URL}")
    print(f"Data: {data}")
    print(f"Headers: {safe_headers}")
    print(f"RO-Crate bytes: {len(rocrate_zip)}")

    try:
        async with httpx.AsyncClient(timeout=15.0) as http_client:
            response = await http_client.post(
                WORKFLOW_API_URL,
                data=data,
                files={
                    "rocratefile": (
                        "rocrate.zip",
                        rocrate_zip,
                        "application/zip",
                    )
                },
                headers=headers,
            )
            print(f"Workflow API response: {response.status_code}")
            response_preview = response.text[:2000]
            print(f"Workflow API body: {response_preview}")
    except httpx.HTTPError as exc:
        print(f"Workflow API exception: {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=502, detail=f"Workflow API error: {exc}") from exc

    if response.status_code >= 300:
        raise HTTPException(
            status_code=502,
            detail=f"Workflow API error: {response.status_code} {response.text}",
        )

    try:
        response_payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Workflow API returned invalid JSON") from exc

    workflow_id = response_payload.get("workflow_id") or response_payload.get("id")
    if not workflow_id:
        raise HTTPException(status_code=502, detail="Workflow API did not return workflow_id")

    print("=" * 60)
    print(f"WORKFLOW SUBMITTED - ID: {workflow_id}")
    print(f"User ID: {user_id}")
    print(f"Name: {workflow.name}")
    print(f"Description: {workflow.description}")
    print(f"Species Name: {workflow.species_name}")
    print(f"Ecosystem Type: {workflow.ecosystem_type}")
    print(f"Geometry Type: {workflow.geometry_type}")
    print(f"Geometry WKT: {workflow.geometry_wkt}")
    print(f"Parameters: {workflow.parameters}")
    print("=" * 60)

    create_workflow(
        workflow_id=workflow_id,
        user_id=user_id,
        name=workflow.name,
        description=workflow.description,
        species_name=workflow.species_name,
        ecosystem_type=workflow.ecosystem_type,
        geometry_type=workflow.geometry_type,
        geometry_wkt=workflow.geometry_wkt,
        parameters=str(workflow.parameters),
        status=response_payload.get("status", "submitted"),
    )

    return {
        "workflow_id": workflow_id,
        "status": response_payload.get("status", "submitted"),
    }


@router.post("/api/workflows/webhook/{workflow_id}")
async def workflow_webhook(workflow_id: str, webhook_data: WorkflowWebhook):
    """Webhook endpoint called by Argo Workflow when job completes."""
    print(f"WEBHOOK RECEIVED for workflow {workflow_id}")
    print(f"Status: {webhook_data.status}")

    if webhook_data.status == "Succeeded":
        update_workflow_status(
            workflow_id,
            "completed",
        )
    elif webhook_data.status == "Failed":
        update_workflow_status(workflow_id, "failed", error=webhook_data.error_message)

    return {"status": "webhook processed"}


@router.get("/api/workflows")
async def api_get_workflows(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user_id = verify_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    workflows = get_user_workflows(user_id)
    return {"workflows": workflows}


@router.get("/api/workflows/{workflow_id}/download")
async def api_download_workflow_results(
    workflow_id: str,
    token: Optional[str] = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
):
    async def _close_stream(response: httpx.Response, client: httpx.AsyncClient) -> None:
        await response.aclose()
        await client.aclose()

    auth_token = None
    if credentials:
        auth_token = credentials.credentials
    elif token:
        auth_token = token

    if not auth_token:
        raise HTTPException(status_code=401, detail="Missing authentication")

    user_id = verify_token(auth_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    workflow = get_workflow_by_id(workflow_id)
    if not workflow or workflow["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Workflow not found")

    headers = build_workflow_api_headers()
    url = f"{WORKFLOW_API_URL}/{workflow_id}/download"
    try:
        http_client = httpx.AsyncClient(timeout=60.0)
        request = http_client.build_request("GET", url, headers=headers)
        response = await http_client.send(request, stream=True)

        if response.status_code >= 300:
            detail = (await response.aread()).decode(errors="replace")[:2000]
            await _close_stream(response, http_client)
            raise HTTPException(
                status_code=502,
                detail=f"Workflow API error: {response.status_code} {detail}",
            )

        content_type = response.headers.get(
            "content-type", "application/octet-stream"
        )
        filename = response.headers.get(
            "content-disposition", "attachment; filename=results.zip"
        )
        return StreamingResponse(
            response.aiter_bytes(),
            media_type=content_type,
            headers={"Content-Disposition": filename},
            background=BackgroundTask(_close_stream, response, http_client),
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Workflow API error: {exc}") from exc


@router.delete("/api/workflows/{workflow_id}")
async def api_delete_workflow(
    workflow_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user_id = verify_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    workflow = get_workflow_by_id(workflow_id)
    if not workflow or workflow["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Workflow not found")

    delete_workflow(workflow_id)
    return {"status": "deleted", "workflow_id": workflow_id}
