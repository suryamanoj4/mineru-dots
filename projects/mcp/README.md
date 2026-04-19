# VParse MCP-Server

## 1. Overview

This project provides a **VParse MCP Server** (`vparse-mcp`), built on the **FastMCP** framework. Its primary function is to serve as an interface for the **VParse API**, used to convert documents into Markdown format.

The server exposes the following main tools via the MCP protocol:

1. `parse_documents`: A unified interface supporting both local files and URLs. It automatically selects the best processing method based on configuration and returns the converted content.
2. `get_ocr_languages`: Retrieves the list of supported OCR languages.

This allows other applications or MCP clients to easily integrate VParse's document-to-Markdown conversion functionality.

## 2. Core Features

* **Document Extraction**: Receives document file input (single or multiple URLs, single or multiple local paths; supports doc, ppt, pdf, and image formats), calls the VParse API for content extraction and format conversion, and finally generates Markdown files.
* **Batch Processing**: Supports simultaneous processing of multiple document files (by providing a list of URLs or local file paths separated by spaces, commas, or newlines).
* **OCR Support**: Optional OCR functionality (disabled by default) to handle scanned or image-based documents.
* **Multi-language Support**: Supports recognition of multiple languages, with auto-detection or manual specification.
* **Automated Workflow**: Automatically handles interactions with the VParse API, including task submission, status polling, result downloading/unzipping, and result file reading.
* **Local Parsing**: Supports calling locally deployed VParse models directly to parse documents without depending on the remote API, suitable for privacy-sensitive scenarios or offline environments.
* **Intelligent Path Handling**: Automatically identifies URLs and local file paths, choosing the most appropriate processing method based on the `USE_LOCAL_API` configuration.

## 3. Installation

Before starting, ensure your system meets the minimum requirements:
* Python >= 3.10

### 3.1 Install via pip (Recommended)

If the package is published to PyPI or another index, install it directly:

```bash
pip install vparse-mcp==1.0.0
# Legacy alias also supported:
# pip install mineru-mcp==1.0.0
```

Current version: 1.0.0

This method is suitable for general users who do not need to modify the source code.

### 3.2 Install from Source

If you need to modify the code or contribute to development, install from source.

Clone the repository and enter the directory:

```bash
git clone <repository-url> # Replace with your repository URL
cd vparse-mcp
```

We recommend using `uv` or `pip` with a virtual environment:

**Using uv (Recommended):**

```bash
# Install uv (if not already installed)
# pip install uv

# Create and activate virtual environment
uv venv

# Linux/macOS
source .venv/bin/activate 
# Windows
# .venv\Scripts\activate

# Install dependencies and project
uv pip install -e .
```

**Using pip:**

```bash
# Create and activate virtual environment
python -m venv .venv

# Linux/macOS
source .venv/bin/activate 
# Windows
# .venv\Scripts\activate

# Install dependencies and project
pip install -e .
```

## 4. Environment Variables

This project is configured via environment variables. You can set them in your system or create a `.env` file in the project root (see `.env.example` as a template).

### 4.1 Supported Variables

| Environment Variable      | Description                                                     | Default Value             |
| ------------------------- | --------------------------------------------------------------- | ------------------------- |
| `VPARSE_API_BASE`       | Base URL for the VParse remote API                              | `https://vparse.net`    |
| `VPARSE_API_KEY`        | VParse API key, required from the [Official Website](https://vparse.net) | -                         |
| `OUTPUT_DIR`            | Path to save converted files                                     | `./downloads`           |
| `USE_LOCAL_API`         | Whether to use a local API for parsing                          | `false`                 |
| `LOCAL_VPARSE_API_BASE` | Base URL for the local API (effective when `USE_LOCAL_API=true`) | `http://localhost:8080` |

### 4.2 Remote API vs. Local API

The project supports two API modes:

* **Remote API**: Default mode, parses documents via the cloud service provided by VParse. Advantages: no need for local deployment of complex models and environments; requires network connection and an API key.
* **Local API**: Deploys the VParse engine locally for document parsing, suitable for scenarios with high data privacy requirements or offline use. Effective when `USE_LOCAL_API=true`.

### 4.3 Get an API Key

To get a `VPARSE_API_KEY`, visit the [VParse Official Website](https://vparse.net) to register an account and apply for an API key.

## 5. Usage

### 5.1 Tool Overview

The following tools are available via the MCP protocol:

1. **parse_documents**: Unified interface for local files and URLs. Automatically handles processing and reads output.
2. **get_ocr_languages**: Retrieves the list of supported OCR languages.

### 5.2 Parameters

#### 5.2.1 parse_documents

| Parameter | Type | Description | Default | Mode |
| --- | --- | --- | --- | --- |
| `file_sources` | String | Paths or URLs (comma/newline separated). Supports PDF, PPT, DOC, and images. | - | All |
| `enable_ocr` | Boolean | Whether to enable OCR | `false` | All |
| `language` | String | Document language (e.g., "ch", "en") | `ch` | All |
| `page_ranges` | String (Opt) | Comma-separated page ranges (e.g., "2,4-6", "2--2"). | `None` | Remote API |

> **Note**:
> - When `USE_LOCAL_API=true`, URLs are filtered out; only local paths are processed.
> - When `USE_LOCAL_API=false`, both URLs and local paths are processed.

#### 5.2.2 get_ocr_languages

No parameters required.

## 6. MCP Client Integration

You can use the VParse MCP server in any client that supports the MCP protocol.

### 6.1 Using with Claude

Configure the VParse MCP server as a tool for Claude to use document-to-Markdown conversion directly. Refer to the MCP tool configuration documentation for details. Depending on your installation, choose one of the following:

#### 6.1.1 Running from Source

If running from source, use the following configuration, suitable for development and debugging:

```json
{
  "mcpServers": {
    "vparse-mcp": {
      "command": "uv",
      "args": ["--directory", "/path/to/vparse-mcp", "run", "-m", "vparse.cli"],
      "env": {
        "VPARSE_API_BASE": "https://vparse.net",
        "VPARSE_API_KEY": "your-api-key",
        "OUTPUT_DIR": "./downloads",
        "USE_LOCAL_API": "true",
        "LOCAL_VPARSE_API_BASE": "http://localhost:8080"
      }
    }
  }
}
```

Features:
- Uses `uv`.
- Explicitly points to the source directory via `--directory`.
- Runs via the `vparse.cli` module.
- Suitable for development and customization.

#### 6.1.2 Installed Package Mode

If installed via pip or uv, use this simpler configuration, suitable for production or daily use:

```json
{
  "mcpServers": {
    "vparse-mcp": {
      "command": "uvx",
      "args": ["vparse-mcp"],
      "env": {
        "VPARSE_API_BASE": "https://vparse.net",
        "VPARSE_API_KEY": "your-api-key",
        "OUTPUT_DIR": "./downloads",
        "USE_LOCAL_API": "true",
        "LOCAL_VPARSE_API_BASE": "http://localhost:8080"
      }
    }
  }
}
```

Features:
- Uses `uvx` for one-command execution.
- Cleaner configuration; no source directory required.

### 6.2 Using with FastMCP Client (Python)

```python
from fastmcp import FastMCP

# Initialize client
client = FastMCP(server_url="http://localhost:8001")

# Single document
result = await client.tool_call(
    tool_name="parse_documents",
    params={"file_sources": "/path/to/document.pdf"}
)

# Mixed URLs and local files
result = await client.tool_call(
    tool_name="parse_documents",
    params={"file_sources": "/path/to/file.pdf, https://example.com/document.pdf"}
)

# Enable OCR
result = await client.tool_call(
    tool_name="parse_documents",
    params={"file_sources": "/path/to/file.pdf", "enable_ocr": True}
)
```

### 6.3 Running the Service Directly

You can start the VParse MCP server by setting environment variables and running the command directly, which is ideal for quick testing and development.

#### 6.3.1 Set Environment Variables

```bash
# Linux/macOS
export VPARSE_API_BASE="https://vparse.net"
export VPARSE_API_KEY="your-api-key"
export OUTPUT_DIR="./downloads"
export USE_LOCAL_API="true"  # Optional, for local parsing
export LOCAL_VPARSE_API_BASE="http://localhost:8080"  # Optional, if local API is enabled

# Windows
set VPARSE_API_BASE=https://vparse.net
set VPARSE_API_KEY=your-api-key
set OUTPUT_DIR=./downloads
set USE_LOCAL_API=true
set LOCAL_VPARSE_API_BASE=http://localhost:8080
```

#### 6.3.2 Start Service

Start the VParse MCP server using the following commands, supporting multiple transport modes:

**SSE Mode**:
```bash
uv run vparse-mcp --transport sse
```

**Streamable HTTP Mode**:
```bash
uv run vparse-mcp --transport streamable-http
```

The service defaults to `http://localhost:8001`. The endpoint depends on the transport:
- SSE: `/sse` (e.g., `http://localhost:8001/sse`)
- Streamable HTTP: `/mcp` (e.g., `http://localhost:8001/mcp`)

## 7. Docker Deployment

Deploy quickly in any Docker environment.

### 7.1 Using Docker Compose

1. Ensure Docker and Docker Compose are installed.
2. Copy `.env.example` to `.env` and modify the environment variables.
3. Start the service:

```bash
docker-compose up -d
```

The service will be available at `http://localhost:8001`.

### 7.2 Manual Build

```bash
docker build -t vparse-mcp:latest .
```

Then start the container:

```bash
docker run -p 8001:8001 --env-file .env vparse-mcp:latest
```

See `DOCKER_README.md` for more details.

## 8. FAQ

### 8.1 API Key Issues
**Issue**: 401 Error or connection failure.
**Solution**: Verify `VPARSE_API_KEY` is set correctly in your environment or `.env` file. Visit the official website to obtain a valid key.

### 8.2 Graceful Exit
**Issue**: How to stop the service correctly?
**Solution**: Press `Ctrl+C` to exit gracefully. The system will handle ongoing operations and release resources. Press twice for forced exit.

### 8.3 File Path Issues
**Issue**: "File not found" error when processing local files.
**Solution**: Ensure you are using absolute paths or correct relative paths relative to the server's running directory.

### 8.4 Request Timeouts
**Issue**: `MCP error -32001: Request timed out`.
**Solution**: Common with large documents or unstable networks. Some clients (like Cursor) may require a restart after a timeout.
1. **Wait for official fix**: Known issue in some clients; wait for updates.
2. **Process smaller files**: Handle small files to avoid timeouts.
3. **Batch processing**: Split multiple files into smaller requests.
4. **Increase timeout**: Adjust client-side settings if supported.
5. **Restart client**: Required for some clients after a timeout.
6. **Use Local API**: Consider Local API mode for heavy workloads or unstable networks.
