"""
server.py — MCP server that exposes role data from a spreadsheet/CSV.

An upstream AI agent connects over HTTP/SSE and can call three tools:
    - search_roles(query, skill=None)   keyword search across open roles
    - get_role(role_id)                 full detail for one role
    - list_open_roles(limit=10)         all roles whose status is "open"

Data source, in priority order:
    1. SPREADSHEET_URL  env var: a public CSV/Excel URL (Google Sheets share
                        links are converted to their CSV export automatically)
    2. DATA_FILE        env var: a local .csv / .xlsx / .xls path
                        (default: roles.csv, then roles.xlsx, next to this file)
    3. A built-in sample dataset, so the server always starts.

Environment:
    HOST            bind address              (default 0.0.0.0)
    PORT            bind port                 (default 8000)
    MCP_TRANSPORT   "sse" or "http"           (default sse)
    SPREADSHEET_URL / DATA_FILE               (see above)

Run:
    pip install fastmcp pandas openpyxl
    python server.py
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import pandas as pd
from fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Maps the standard field names used by this server (keys) to the actual
# column headers in your spreadsheet (values). Edit the values to match your
# sheet; header matching is case- and whitespace-insensitive.
COLUMNS: dict[str, str] = {
    "role_id": "Role ID",
    "title": "Job Title",
    "skills": "Required Skills",
    "status": "Status",
    "description": "Description",
    "location": "Location",
}

# Status values (lower-cased) that count as "open".
OPEN_STATUSES = {"open", "active", "hiring", "accepting applications"}

# Upper bound for list_open_roles so a single call can't dump a huge sheet.
MAX_LIMIT = 100

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
TRANSPORT = os.getenv("MCP_TRANSPORT", "sse").lower()
SPREADSHEET_URL = os.getenv("SPREADSHEET_URL", "").strip()
DATA_FILE = os.getenv("DATA_FILE", "").strip()

BASE_DIR = Path(__file__).resolve().parent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("roles-mcp")

# ---------------------------------------------------------------------------
# Sample fallback dataset (uses the spreadsheet header names from COLUMNS)
# ---------------------------------------------------------------------------

_SAMPLE_ROWS = [
    {
        "role_id": "R-001",
        "title": "Senior Backend Engineer",
        "skills": "Python, FastAPI, PostgreSQL, AWS",
        "status": "Open",
        "description": "Design and scale the APIs that power our core platform.",
        "location": "Remote (US)",
    },
    {
        "role_id": "R-002",
        "title": "Frontend Engineer",
        "skills": "TypeScript, React, CSS, Accessibility",
        "status": "Open",
        "description": "Build fast, accessible interfaces for our customer dashboard.",
        "location": "London, UK",
    },
    {
        "role_id": "R-003",
        "title": "Data Scientist",
        "skills": "Python, pandas, SQL, Machine Learning",
        "status": "Closed",
        "description": "Model customer behaviour and drive product experiments.",
        "location": "New York, NY",
    },
    {
        "role_id": "R-004",
        "title": "DevOps Engineer",
        "skills": "Kubernetes, Terraform, AWS, CI/CD",
        "status": "Open",
        "description": "Own our infrastructure, deployments and observability stack.",
        "location": "Remote (EU)",
    },
    {
        "role_id": "R-005",
        "title": "Product Designer",
        "skills": "Figma, User Research, Prototyping",
        "status": "On Hold",
        "description": "Shape end-to-end product experiences with research and design.",
        "location": "Berlin, Germany",
    },
]


def _sample_dataframe() -> pd.DataFrame:
    """Build the fallback dataset using the real header names from COLUMNS."""
    return pd.DataFrame(
        [{COLUMNS[field]: value for field, value in row.items()} for row in _SAMPLE_ROWS]
    )


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _google_sheet_to_csv_url(url: str) -> str:
    """Turn a Google Sheets share/edit link into its CSV export link."""
    match = re.search(r"docs\.google\.com/spreadsheets/d/([\w-]+)", url)
    if not match or "export?format=csv" in url:
        return url
    gid = re.search(r"[#&?]gid=(\d+)", url)
    export = f"https://docs.google.com/spreadsheets/d/{match.group(1)}/export?format=csv"
    return export + (f"&gid={gid.group(1)}" if gid else "")


def _read_table(source: str) -> pd.DataFrame:
    """Read a CSV or Excel file from a local path or URL, chosen by extension."""
    lowered = source.lower().split("?")[0]
    if lowered.endswith((".xlsx", ".xls")):
        return pd.read_excel(source, dtype=str)
    return pd.read_csv(source, dtype=str)


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    """Rename spreadsheet headers to standard field names and clean values.

    Columns listed in COLUMNS but missing from the sheet are added as empty,
    so tools degrade gracefully instead of raising KeyError.
    """
    lookup = {str(col).strip().lower(): col for col in df.columns}
    rename = {}
    for field, header in COLUMNS.items():
        actual = lookup.get(header.strip().lower())
        if actual is not None:
            rename[actual] = field
        else:
            log.warning("Column %r (for %r) not found in data; using blanks.", header, field)

    df = df.rename(columns=rename)
    for field in COLUMNS:
        if field not in df.columns:
            df[field] = ""

    df = df.fillna("").astype(str).apply(lambda s: s.str.strip())
    # Drop rows without an ID — they can't be addressed by get_role.
    return df[df["role_id"] != ""].reset_index(drop=True)


def load_roles() -> tuple[pd.DataFrame, str]:
    """Load the dataset, returning (dataframe, human-readable source label)."""
    if SPREADSHEET_URL:
        url = _google_sheet_to_csv_url(SPREADSHEET_URL)
        try:
            return _normalise(_read_table(url)), f"url:{SPREADSHEET_URL}"
        except Exception as exc:  # network, parse, auth errors, etc.
            log.error("Failed to load SPREADSHEET_URL (%s); trying local file.", exc)

    candidates = [Path(DATA_FILE)] if DATA_FILE else [BASE_DIR / "roles.csv", BASE_DIR / "roles.xlsx"]
    for path in candidates:
        if path.is_file():
            try:
                return _normalise(_read_table(str(path))), f"file:{path}"
            except Exception as exc:
                log.error("Failed to load %s (%s).", path, exc)

    log.warning("No data source available; using built-in sample dataset.")
    return _normalise(_sample_dataframe()), "sample"


ROLES, DATA_SOURCE = load_roles()
log.info("Loaded %d roles from %s", len(ROLES), DATA_SOURCE)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_open(status: str) -> bool:
    return status.strip().lower() in OPEN_STATUSES


def _open_roles() -> pd.DataFrame:
    return ROLES[ROLES["status"].map(_is_open)]


def _summary(row: pd.Series) -> dict[str, str]:
    """Compact view of a role for list/search results."""
    return {k: row[k] for k in ("role_id", "title", "location", "status", "skills")}


def _detail(row: pd.Series) -> dict[str, str]:
    """Full view of a role: every column in the sheet, standard fields first."""
    ordered = list(COLUMNS) + [c for c in row.index if c not in COLUMNS]
    return {str(k): row[k] for k in ordered}


def _error(message: str) -> dict[str, Any]:
    return {"ok": False, "error": message}


# ---------------------------------------------------------------------------
# MCP server and tools
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="roles-server",
    instructions=(
        "Query available job roles. Use list_open_roles to browse, "
        "search_roles to find roles by keyword or skill, and get_role "
        "for full details of a specific role_id."
    ),
)


@mcp.tool
def search_roles(query: str, skill: str | None = None) -> dict[str, Any]:
    """Search open roles by keyword, optionally filtered by a required skill.

    Every word in `query` must appear in the role's title, skills or
    description (case-insensitive). If `skill` is given, the role's skills
    column must also contain it.

    Args:
        query: Keywords to search for, e.g. "backend python".
        skill: Optional single skill to require, e.g. "AWS".
    """
    try:
        query = (query or "").strip()
        skill = (skill or "").strip()
        if not query and not skill:
            return _error("Provide a non-empty 'query' or 'skill'.")

        roles = _open_roles()
        haystack = (roles["title"] + " " + roles["skills"] + " " + roles["description"]).str.lower()

        mask = pd.Series(True, index=roles.index)
        for term in query.lower().split():
            mask &= haystack.str.contains(term, regex=False)
        if skill:
            mask &= roles["skills"].str.lower().str.contains(skill.lower(), regex=False)

        matches = [_summary(row) for _, row in roles[mask].iterrows()]
        return {"ok": True, "query": query, "skill": skill or None, "count": len(matches), "roles": matches}
    except Exception as exc:
        log.exception("search_roles failed")
        return _error(f"Search failed: {exc}")


@mcp.tool
def get_role(role_id: str) -> dict[str, Any]:
    """Return full details for a single role by its unique ID.

    Args:
        role_id: The role's identifier, e.g. "R-001" (case-insensitive).
    """
    try:
        role_id = (role_id or "").strip()
        if not role_id:
            return _error("'role_id' must be a non-empty string.")

        hit = ROLES[ROLES["role_id"].str.lower() == role_id.lower()]
        if hit.empty:
            return _error(f"No role found with role_id '{role_id}'.")
        return {"ok": True, "role": _detail(hit.iloc[0])}
    except Exception as exc:
        log.exception("get_role failed")
        return _error(f"Lookup failed: {exc}")


@mcp.tool
def list_open_roles(limit: int = 10) -> dict[str, Any]:
    """List roles whose status marks them as open.

    Args:
        limit: Maximum number of roles to return (1-100, default 10).
    """
    try:
        if not isinstance(limit, int) or limit < 1:
            return _error("'limit' must be a positive integer.")
        limit = min(limit, MAX_LIMIT)

        roles = _open_roles()
        items = [_summary(row) for _, row in roles.head(limit).iterrows()]
        return {"ok": True, "total_open": len(roles), "returned": len(items), "roles": items}
    except Exception as exc:
        log.exception("list_open_roles failed")
        return _error(f"Listing failed: {exc}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if TRANSPORT not in {"sse", "http"}:
        raise SystemExit(f"Unsupported MCP_TRANSPORT {TRANSPORT!r}; use 'sse' or 'http'.")
    path = "/sse" if TRANSPORT == "sse" else "/mcp"
    log.info("Starting MCP server (%s) on http://%s:%d%s", TRANSPORT, HOST, PORT, path)
    mcp.run(transport=TRANSPORT, host=HOST, port=PORT)
