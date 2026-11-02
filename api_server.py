"""Browser-facing read-only API for the ProjectHub frontend.

Keep this file in the SAME folder as your existing server.py.
It imports server.py, reuses its spreadsheet loading and role-normalisation
logic, and leaves the three existing FastMCP tools unchanged.
"""

from typing import Any
import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import server as roles_server  # Your existing MCP server file: server.py

app = FastAPI(title="ProjectHub API", version="1.0.0")

# Development setting for Live Server. Do not use wildcard CORS for a public
# production deployment; restrict this to your trusted Teams/app origins then.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


def _key(value: Any) -> str:
    """Make column labels comparable despite spaces/underscores/case."""
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _pick(record: dict[str, Any], *names: str, default: str = "") -> str:
    wanted = {_key(name) for name in names}
    for key, value in record.items():
        if _key(key) in wanted and str(value or "").strip():
            return str(value).strip()
    return default


def _split_skills(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,;\n|]", value or "") if part.strip()]


def _to_project(record: dict[str, Any], index: int) -> dict[str, Any]:
    """Adapt the spreadsheet's role fields to the frontend's project fields."""
    skills_text = _pick(record, "skills", "required skills", default="")
    created_at = _pick(record, "createdAt", "created at", "date created", "created on", "posted date", default="")
    palette = ["purple", "blue", "green", "orange", "pink", "teal"]
    symbols = ["▦", "◇", "↗", "◎", "⌁", "▥"]
    return {
        "id": _pick(record, "role_id", "role id", "id", default=f"ROLE-{index + 1:03d}"),
        "title": _pick(record, "title", "job title", "project title", default="Untitled opportunity"),
        "team": _pick(record, "team", "department", "team / department", "business unit", default="Internal project"),
        "manager": _pick(record, "manager", "project manager", "lead", "owner", default="Not specified"),
        "description": _pick(
    record,
    "description",
    "client_project",
    "project description",
    "role description",
    default="No description provided.",
),
        "skills": _split_skills(skills_text),
        "location": _pick(record, "location", "location type", "work location", default="Not specified"),
        "duration": _pick(record, "duration", "expected duration", "project duration", default="Not specified"),
        "status": _pick(record, "status", default="Open"),
        "createdAt": created_at,
        "symbol": symbols[index % len(symbols)],
        "color": palette[index % len(palette)],
    }


@app.get("/api/health")
def health() -> dict[str, Any]:
    """Small status endpoint used to confirm the API and data source."""
    source = str(getattr(roles_server, "DATA_SOURCE", "sample"))
    if source.startswith("url:"):
        source_type = "spreadsheet_url"
    elif source.startswith("file:"):
        source_type = "local_file"
    else:
        source_type = "sample_data"

    open_count = len(roles_server._open_roles())
    return {
        "ok": True,
        "data_source": source_type,
        "loaded_rows": int(len(roles_server.ROLES)),
        "open_roles": int(open_count),
    }


@app.get("/api/projects")
def get_projects() -> dict[str, Any]:
    """Return open spreadsheet rows in the format expected by ProjectHub."""
    try:
        open_rows = roles_server._open_roles()
        projects = []
        for index, (_, row) in enumerate(open_rows.iterrows()):
            # _detail is an existing helper in server.py; it keeps extra columns
            # from the sheet as well as the standard fields.
            record = roles_server._detail(row)
            projects.append(_to_project(record, index))
        return {"ok": True, "count": len(projects), "projects": projects}
    except Exception as exc:
        # Log details on the server, but return a clear, non-sensitive message.
        roles_server.log.exception("ProjectHub API could not load projects")
        return {"ok": False, "error": "Could not read project data. Check the Python terminal for details."}
