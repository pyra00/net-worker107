# Roles MCP Server

A Model Context Protocol (MCP) server that exposes endpoints to query and retrieve open project roles from a spreadsheet. Designed for integration with an AI consultant matching system via Microsoft Teams.

## Features & Tools Exposed

* `search_roles(query: str, limit: int = 5)`: Search open roles using keywords.
* `get_role(role_id: str)`: Fetch detailed information for a specific role ID.
* `list_open_roles(status: str = "Open")`: List all available open roles.

## Configuration

The server expects spreadsheet column mappings configured via the `COLUMNS` environment variable (JSON string or dict mapping).

### Environment Variables

* `SPREADSHEET_URL`: URL or path to the project roles spreadsheet/CSV.
* `COLUMNS`: JSON mapping standard role keys to spreadsheet column headers.
* `PORT`: Port on which the HTTP server listens (default: `8000`).

## Deployment

1. Deploy this repository to a cloud host (Render, Railway, or Heroku).
2. Set environment variables in your deployment dashboard.
3. Access the live server URL.
