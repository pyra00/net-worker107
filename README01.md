# Roles MCP Server

A small [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server, built with [FastMCP](https://gofastmcp.com), that lets an AI agent query job roles stored in a spreadsheet or CSV.

It exposes three tools:

| Tool | What it does |
| --- | --- |
| `search_roles(query, skill=None)` | Keyword search across **open** roles (title, skills, description). Every word in `query` must match; `skill` optionally requires a specific skill. |
| `get_role(role_id)` | Full details for one role by its ID (case-insensitive). |
| `list_open_roles(limit=10)` | Lists roles whose status is open (max 100 per call). |

Every tool returns JSON. On bad input it returns `{"ok": false, "error": "..."}` instead of crashing.

---

## Run it on your machine

### 1. Prerequisites

- **Python 3.10 or newer** — check with `python --version` (on macOS/Linux you may need `python3`)
- **Git**

### 2. Clone the repo

```bash
git clone https://github.com/pyra00/net-worker107.git
cd net-worker107
```

### 3. Create a virtual environment and install dependencies

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> If PowerShell blocks the activate script, run this once and try again:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

You should see `(.venv)` at the start of your terminal prompt. Activate the environment again each time you open a new terminal.

### 4. Start the server

**Windows (PowerShell)**

```powershell
$env:HOST = "127.0.0.1"; python server.py
```

**macOS / Linux**

```bash
HOST=127.0.0.1 python server.py
```

When it's running you'll see:

```
INFO Starting MCP server (sse) on http://127.0.0.1:8000/sse
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Leave this terminal open — the server runs until you stop it.

> Setting `HOST=127.0.0.1` keeps the server reachable only from your own computer. Without it, the server listens on `0.0.0.0` (all network interfaces), which is what you want when deploying, not for local testing.

### 5. Check that it's live

Open a **second** terminal in the same folder, activate the virtual environment (step 3), and run:

```bash
python test_client.py
```

Expected output:

```
Connected to http://127.0.0.1:8000/sse
Tools: search_roles, get_role, list_open_roles

list_open_roles({'limit': 3}) ->
  {'ok': True, 'total_open': 3, ...}
...
```

You can also open <http://127.0.0.1:8000/sse> in a browser: you should see `event: endpoint` and the page will keep loading (the connection stays open on purpose).

### 6. Stop the server

Go back to the server's terminal and press **Ctrl+C**. A `KeyboardInterrupt` message is normal.

---

## Use your own role data

Out of the box the server uses a built-in sample of 5 roles, so it always starts. To use real data:

1. Copy the template:
   ```bash
   cp roles.example.csv roles.csv          # macOS / Linux
   copy roles.example.csv roles.csv        # Windows
   ```
2. Fill in `roles.csv` (or use `roles.xlsx` instead).
3. Restart the server. The log will say `Loaded N roles from file:...roles.csv`.

`roles.csv` and `roles.xlsx` are in `.gitignore`, so your local data is never committed.

**Different column names?** Edit the `COLUMNS` dictionary near the top of `server.py`. Keys are the fields the server uses; values are your spreadsheet's header names (matching ignores case and extra spaces):

```python
COLUMNS = {
    "role_id": "Role ID",
    "title": "Job Title",
    "skills": "Required Skills",
    "status": "Status",
    "description": "Description",
    "location": "Location",
}
```

A role counts as **open** if its status is one of `OPEN_STATUSES` in `server.py` (`open`, `active`, `hiring`, `accepting applications`). Add your own wording there if needed.

---

## Configuration

All settings are environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `HOST` | `0.0.0.0` | Address to bind. Use `127.0.0.1` for local-only. |
| `PORT` | `8000` | Port to listen on. |
| `MCP_TRANSPORT` | `sse` | `sse` (endpoint `/sse`) or `http` (streamable HTTP, endpoint `/mcp`). |
| `SPREADSHEET_URL` | — | Public CSV/Excel URL. Google Sheets share links work (the sheet must be viewable by anyone with the link). |
| `DATA_FILE` | `roles.csv`, then `roles.xlsx` | Path to a local CSV/Excel file. |

Data is loaded in this order: `SPREADSHEET_URL` → local file → built-in sample. If a source fails, the server logs why and moves to the next one.

---

## Connect an AI client

With the server running, point your MCP client at `http://127.0.0.1:8000/sse`.
**DONT TOUCH YET**
**Claude Code**

```bash
claude mcp add --transport sse roles http://127.0.0.1:8000/sse
```

**VS Code (GitHub Copilot agent mode)** — create `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "roles": {
      "type": "sse",
      "url": "http://127.0.0.1:8000/sse"
    }
  }
}
```

---

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `ModuleNotFoundError: No module named 'fastmcp'` | The virtual environment isn't active. Activate it (step 3) and try again. |
| `error while attempting to bind ... 8000` / "address already in use" | Something is already on port 8000, often an old copy of this server. Stop it, or use another port: `PORT=8001`. Then use `python test_client.py http://127.0.0.1:8001/sse`. |
| `Could not reach the server` from `test_client.py` | Make sure `python server.py` is still running in the other terminal. |
| Log says `using built-in sample dataset` | No `roles.csv`/`roles.xlsx` was found and no `SPREADSHEET_URL` was set. See *Use your own role data*. |
| Log says `Column 'X' not found in data` | A header in your sheet doesn't match `COLUMNS`. Update `COLUMNS` in `server.py`. |

---

## Project files

```
server.py            MCP server and the three tools
test_client.py       Connects to a running server and calls each tool
requirements.txt     Python dependencies
roles.example.csv    Template for your own role data
```
