# VParse MCP-Server Docker 部署指南

## 1. Introduction

本文档提供了使用 Docker 部署 VParse MCP-Server 的详细指南。通过 Docker 部署，你可以在任何支持 Docker 的环境中快速启动 VParse MCP 服务器，无需考虑复杂的环境配置和依赖管理。

Key advantages of Docker deployment:

- **Consistent Environment**: Ensures identical runtime environments across all platforms.
- **Simplified Deployment**: One-click startup without manual dependency installation.
- **Easy Scaling and Migration**: Facilitates service migration and scaling across different environments.
- **Resource Isolation**: Prevents conflicts with other services on the host machine.

## 2. Prerequisites

Before starting, ensure your system has the following software installed:

- [Docker](https://www.docker.com/get-started) (19.03 or higher)
- [Docker Compose](https://docs.docker.com/compose/install/) (1.27.0 or higher)

You can check if they are correctly installed using:

```bash
docker --version
docker-compose --version
```

Additionally, you will need:

- 从 [VParse 官网](https://vparse.net) 获取的 API 密钥（如果需要使用远程 API）
- 充足的硬盘空间，用于存储转换后的文件

## 3. Deploying with Docker Compose (Recommended)

Docker Compose provides the simplest deployment method, ideal for a quick start or development environments.

### 3.1 Prepare Configuration

1. Clone the repository (if not already done):

   ```bash
   git clone <repository-url>
   cd vparse-mcp
   ```

2. Create an environment variable file:

   ```bash
   cp .env.example .env
   ```

3. Edit the `.env` file and set the necessary environment variables:

   ```
   VPARSE_API_BASE=https://vparse.net
   VPARSE_API_KEY=你的API密钥
   OUTPUT_DIR=./downloads
   USE_LOCAL_API=false
   LOCAL_VPARSE_API_BASE=http://localhost:8080
   ```

   如果你计划使用本地 API，请将 `USE_LOCAL_API` 设置为 `true`，并确保 `LOCAL_VPARSE_API_BASE` 指向你的本地 API 服务地址。

### 3.2 Start the Service

Run the following in the project root:

```bash
docker-compose up -d
```

This will:
- Build the Docker image (if not already built).
- Create and start the container.
- Run the service in the background (`-d` flag).

The service will start at `http://localhost:8001`. You can connect to this address via an MCP client.

### 3.3 View Logs

To view service logs, run:

```bash
docker-compose logs -f
```

Press `Ctrl+C` to exit log viewing.

### 3.4 Stop the Service

To stop the service, run:

```bash
docker-compose down
```

If you also want to remove the built images, use:

```bash
docker-compose down --rmi local
```

## 4. Manual Build and Run

If you need more control or customization, you can build and run the Docker image manually.

### 4.1 Build the Image

Run the following in the project root:

```bash
docker build -t vparse-mcp:latest .
```

这将根据 Dockerfile 构建一个名为 `vparse-mcp` 的 Docker 镜像，标签为 `latest`。

### 4.2 Run the Container

Run the container using an environment variable file:

```bash
docker run -p 8001:8001 --env-file .env vparse-mcp:latest
```

Alternatively, specify environment variables directly:

```bash
docker run -p 8001:8001 \
  -e VPARSE_API_BASE=https://vparse.net \
  -e VPARSE_API_KEY=你的API密钥 \
  -e OUTPUT_DIR=/app/downloads \
  -v $(pwd)/downloads:/app/downloads \
  vparse-mcp:latest
```

### 4.3 Mount Volumes

For persistent storage of converted files, mount a host directory to the container's output directory:

```bash
docker run -p 8001:8001 --env-file .env \
  -v $(pwd)/downloads:/app/downloads \
  vparse-mcp:latest
```

This mounts the `downloads` folder in your current working directory to `/app/downloads` inside the container.

## 5. Environment Configuration

Supported environment variables in Docker are the same as in a standard environment:

| 环境变量 | 说明 | 默认值 |
| ------------------------- | -------------------------------------------------------------- | ------------------------- |
| `VPARSE_API_BASE` | VParse 远程 API 的基础 URL | `https://vparse.net` |
| `VPARSE_API_KEY` | VParse API 密钥，需要从官网申请 | - |
| `OUTPUT_DIR` | 转换后文件的保存路径 | `/app/downloads` |
| `USE_LOCAL_API` | 是否使用本地 API 进行解析（仅适用于 `local_parse_pdf` 工具） | `false` |
| `LOCAL_VPARSE_API_BASE` | 本地 API 的基础 URL（当 `USE_LOCAL_API=true` 时有效） | `http://localhost:8080` |

In a Docker environment, you can:

- Specify an environment file via `--env-file`.
- Pass variables directly using the `-e` flag.
- Configure variables in the `environment` section of `docker-compose.yml`.
