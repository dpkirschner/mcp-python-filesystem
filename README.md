# mcp-python-filesystem

A Python MCP server for filesystem operations using FastMCP.

## Features

- Secure filesystem access with directory whitelisting
- File operations (read, write, edit, get info)
- Directory listing capabilities
- PDF file handling
- FastMCP protocol support
- Verbose logging for debugging

## Setup

1. Ensure Python 3.12 is installed
2. Clone this repository (if applicable)
3. Navigate to the project directory: `cd mcp-python-filesystem`
4. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
5. Install dependencies:
   ```bash
   pip install -e .
   ```

## Running the Server

The server can be run using Python directly:

```bash
python -m src.filesystem.server.main [allowed_directory]... [--verbose]
```

### Arguments

- `allowed_directory`: One or more root directories that the server is allowed to access
- `--verbose`: Enable detailed logging for debugging purposes

### Example Usage

Run with a single directory:
```bash
python -m src.filesystem.server.main /path/to/directory
```

Run with multiple directories:
```bash
python -m src.filesystem.server.main /path/to/dir1 /path/to/dir2
```

Run with verbose logging:
```bash
python -m src.filesystem.server.main /path/to/directory --verbose
```