# VParse MCP-Server

## 1. Overview

这个项目提供了一个 **VParse MCP 服务器** (`vparse-mcp`)，它基于 **FastMCP** 框架构建。其主要功能是作为 **VParse API** 的接口，用于将文档转换为 Markdown格式。

The server exposes the following main tools via the MCP protocol:

1. `parse_documents`: A unified interface supporting both local files and URLs. it automatically selects the best processing method based on configuration and returns the converted content.
2. `get_ocr_languages`: Retrieves the list of supported OCR languages.

这使得其他应用程序或 MCP 客户端能够轻松地集成 VParse 的 文档 到 Markdown 转换功能。

## 2. Core Features

* **文档提取**: 接收文档文件输入（单个或多个 URL、单个或多个本地路径，支持doc、ppt、pdf、图片多种格式），调用 VParse API 进行内容提取和格式转换，最终生成 Markdown 文件。
* **批量处理**: 支持同时处理多个文档文件（通过提供由空格、逗号或换行符分隔的 URL 列表或本地文件路径列表）。
* **OCR 支持**: 可选启用 OCR 功能（默认不开启），以处理扫描版或图片型文档。
* **多语言支持**: 支持多种语言的识别，可以自动检测文档语言或手动指定。
* **自动化流程**: 自动处理与 VParse API 的交互，包括任务提交、状态轮询、结果下载解压、结果文件读取。
* **本地解析**: 支持调用本地部署的vparse模型直接解析文档，不依赖远程 API，适用于隐私敏感场景或离线环境。
* **智能路径处理**: 自动识别URL和本地文件路径，根据USE_LOCAL_API配置选择最合适的处理方式。

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
git clone <repository-url> # 替换为你的仓库 URL
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

| 环境变量                  | 说明                                                            | 默认值                    |
| ------------------------- | --------------------------------------------------------------- | ------------------------- |
| `VPARSE_API_BASE`       | VParse 远程 API 的基础 URL                                      | `https://vparse.net`    |
| `VPARSE_API_KEY`        | VParse API 密钥，需要从[官网](https://vparse.net)申请              | -                         |
| `OUTPUT_DIR`            | 转换后文件的保存路径                                            | `./downloads`           |
| `USE_LOCAL_API`         | 是否使用本地 API 进行解析                                      | `false`                 |
| `LOCAL_VPARSE_API_BASE` | 本地 API 的基础 URL（当 `USE_LOCAL_API=true` 时有效）         | `http://localhost:8080` |

### 4.2 Remote API vs. Local API

The project supports two API modes:

* **远程 API**：默认模式，通过 VParse 官方提供的云服务进行文档解析。优点是无需本地部署复杂的模型和环境，但需要网络连接和 API 密钥。
* **本地 API**：在本地部署 VParse 引擎进行文档解析，适用于对数据隐私有高要求或需要离线使用的场景。设置 `USE_LOCAL_API=true` 时生效。

### 4.3 Get an API Key

要获取 `VPARSE_API_KEY`，请访问 [VParse 官网](https://vparse.net) 注册账号并申请 API 密钥。

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

你可以在任何支持 MCP 协议的客户端中使用 VParse MCP 服务器。

### 6.1 Using with Claude

将 VParse MCP 服务器配置为 Claude 的工具，即可在 Claude 中直接使用文档转 Markdown 功能。配置工具时详情请参考 MCP 工具配置文档。根据不同的安装和使用场景，你可以选择以下两种配置方式：

#### 6.1.1 Running from Source

如果你是从源码安装并运行 VParse MCP，可以使用以下配置。这种方式适合你需要修改源码或者进行开发调试的场景：

```json
{
  "mcpServers": {
    "vparse-mcp": {
      "command": "uv",
      "args": ["--directory", "/Users/adrianwang/Documents/minerU-mcp", "run", "-m", "vparse.cli"],
      "env": {
        "VPARSE_API_BASE": "https://vparse.net",
        "VPARSE_API_KEY": "ey...",
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
- Runs via the `mineru.cli` module.

- 使用 `uv` 命令
- 通过 `--directory` 参数指定源码所在目录
- 使用 `-m vparse.cli` 运行模块
- 适合开发调试和定制化需求

#### 6.1.2 安装包运行方式

如果你是通过 pip 或 uv 安装了 vparse-mcp 包，可以使用以下更简洁的配置。这种方式适合生产环境或日常使用：

```json
{
  "mcpServers": {
    "vparse-mcp": {
      "command": "uvx",
      "args": ["vparse-mcp"],
      "env": {
        "VPARSE_API_BASE": "https://vparse.net",
        "VPARSE_API_KEY": "ey...",
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

你可以通过设置环境变量并直接运行命令的方式启动 VParse MCP 服务器，这种方式特别适合快速测试和开发环境。

#### 6.3.1 Set Environment Variables

```bash
# Linux/macOS
export VPARSE_API_BASE="https://vparse.net"
export VPARSE_API_KEY="your-api-key"
export OUTPUT_DIR="./downloads"
export USE_LOCAL_API="true"  # 可选，如果需要本地解析
export LOCAL_VPARSE_API_BASE="http://localhost:8080"  # 可选，如果启用本地 API

# Windows
set VPARSE_API_BASE=https://vparse.net
set VPARSE_API_KEY=your-api-key
set OUTPUT_DIR=./downloads
set USE_LOCAL_API=true
set LOCAL_VPARSE_API_BASE=http://localhost:8080
```

#### 6.3.2 Start Service

使用以下命令启动 VParse MCP 服务器，支持多种传输模式：

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

```bash
vparse-mcp --transport sse
# 或
vparse-mcp --transport streamable-http
```

Deploy quickly in any Docker environment.

### 7.1 Using Docker Compose


## 7. Docker 部署

本项目支持使用 Docker 进行部署，使你能在任何支持 Docker 的环境中快速启动 VParse MCP 服务器。

### 7.1 使用 Docker Compose

1. 确保你已经安装了 Docker 和 Docker Compose
2. 复制项目根目录中的 `.env.example` 文件为 `.env`，并根据你的需求修改环境变量
3. 运行以下命令启动服务：

```bash
docker-compose up -d
```

The service will be available at `http://localhost:8001`.

### 7.2 Manual Build

```bash
docker build -t vparse-mcp:latest .
```

然后启动容器：

```bash
docker run -p 8001:8001 --env-file .env vparse-mcp:latest
```

See `DOCKER_README.md` for more details.

## 8. FAQ

### 8.1 API Key Issues
**Issue**: 401 Error or connection failure.
**Solution**: Verify `MINERU_API_KEY` is set correctly in your environment or `.env` file.

**问题**：无法连接 VParse API 或返回 401 错误。
**解决方案**：检查你的 API 密钥是否正确设置。在 `.env` 文件中确保 `VPARSE_API_KEY` 环境变量包含有效的密钥。

### 8.2 如何优雅退出服务

**问题**：如何正确地停止 VParse MCP 服务？
**解决方案**：服务运行时，可以通过按 `Ctrl+C` 来优雅地退出。系统会自动处理正在进行的操作，并确保所有资源得到正确释放。如果一次 `Ctrl+C` 没有响应，可以再次按下 `Ctrl+C` 强制退出。

### 8.3 文件路径问题

**问题**：使用 `parse_documents` 工具处理本地文件时报找不到文件错误。
**解决方案**：请确保使用绝对路径，或者相对于服务器运行目录的正确相对路径。

### 8.4 MCP 服务调用超时问题

**问题**：调用 `parse_documents` 工具时出现 `Error calling tool 'parse_documents': MCP error -32001: Request timed out` 错误。
**解决方案**：这个问题常见于处理大型文档或网络不稳定的情况。在某些 MCP 客户端（如 Cursor）中，超时后可能导致无法再次调用 MCP 服务，需要重启客户端。最新版本的 Cursor 中可能会显示正在调用 MCP，但实际上没有真正调用成功。建议：
1. **等待官方修复**：这是Cursor客户端的已知问题，建议等待Cursor官方修复
2. **处理小文件**：尽量只处理少量小文件，避免处理大型文档导致超时
3. **分批处理**：将多个文件分成多次请求处理，每次只处理一两个文件
4. 增加超时时间设置（如果客户端支持）
5. 对于超时后无法再次调用的问题，需要重启 MCP 客户端
6. 如果反复出现超时，请检查网络连接或考虑使用本地 API 模式

### 8.4 Request Timeouts
**Issue**: `MCP error -32001: Request timed out`.
**Solution**: Common with large documents or unstable networks. Some clients (like Cursor) may require a restart after a timeout.
1. Process smaller files.
2. Batch files into multiple smaller requests.
3. Increase client-side timeout settings if available.
4. Consider using Local API mode for heavy workloads.
