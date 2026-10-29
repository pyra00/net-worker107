# ProjectHub — connect the frontend to your spreadsheet

This integration keeps your existing `server.py` and its FastMCP tools unchanged. It adds a small read-only HTTP API for the browser frontend.

## Folder setup

1. Extract this ZIP.
2. Copy `api_server.py` and `requirements-api.txt` into the SAME folder as your existing `server.py`.
3. Copy the three files from `frontend/` into the frontend folder you already use (`index.html`, `styles.css`, `app.js`). You can keep a backup of your current files first.
4. Make sure your existing `server.py` is configured to read the real spreadsheet. It should already use `SPREADSHEET_URL` or `DATA_FILE`. If you set `SPREADSHEET_URL` in a PowerShell terminal before starting the MCP server, set it again in the second terminal too; environment variables are per terminal session. If it is currently falling back to sample data, fix that first.

## Install the API dependencies

Open a terminal in the folder containing `server.py`, activate your existing virtual environment if you have one, then run:

```powershell
python -m pip install -r requirements-api.txt
```

## Start both servers

**Terminal 1 — existing MCP server:** keep running your usual command, for example:

```powershell
python server.py
```

Do not replace `server.py`; its existing `search_roles`, `get_role`, and `list_open_roles` tools remain in place.

**Terminal 2 — browser API:** from the same folder as `api_server.py`, run:

```powershell
python -m uvicorn api_server:app --host 127.0.0.1 --port 8001 --reload
```

## Test the API

Open these URLs in your browser:

- `http://127.0.0.1:8001/api/health` — should show `ok: true` and `data_source: spreadsheet_url` or `local_file`.
- `http://127.0.0.1:8001/api/projects` — should return your open spreadsheet rows as JSON.

If health says `sample_data`, the API is running but `server.py` did not load the configured spreadsheet. Check the spreadsheet URL, permissions, and the server terminal logs.

## Open the frontend

Start VS Code Live Server on `frontend/index.html`. The dashboard requests data from `http://127.0.0.1:8001/api`.

## Important limitations for this stage

- This API is read-only. The Publish form explains that it does not yet write to the spreadsheet.
- This is for local development only. Before a real Microsoft Teams/company rollout, use HTTPS, restrict CORS, add authentication/authorization, and use an approved secure way to write project records.
- The spreadsheet must be readable by the Python process. Public Google Sheets links are converted to CSV by your existing `server.py`; private sheets may need a separate authenticated integration.
