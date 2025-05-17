# mcp-python-filesystem

A Python MCP server for filesystem operations.

## Setup

1.  Ensure Python 3.8+ and `uv` are installed.
2.  Clone this repository (if applicable).
3.  Navigate to the project directory: `cd mcp-python-filesystem`
4.  Create and activate a virtual environment:
    ```bash
    uv venv
    source .venv/bin/activate # (or .venv\Scripts\activate on Windows)
    ```
5.  Install dependencies:
    ```bash
    uv pip install -e .
    ```

## Running the Server

You can run the server using the script defined in `pyproject.toml`:

```bash
filesystem-server [path_to_serve] [--ignore "*.log"]