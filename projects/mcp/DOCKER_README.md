# VParse MCP-Server Docker Deployment Guide

## 1. Introduction

This document provides a detailed guide for deploying VParse MCP-Server using Docker. By deploying via Docker, you can quickly start the VParse MCP server in any environment that supports Docker, without worrying about complex environment configurations and dependency management.

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

- An API key obtained from the [VParse Official Website](https://vparse.net) (if using the remote API)
- Sufficient disk space to store converted files

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
   VPARSE_API_KEY=your_api_key_here
   OUTPUT_DIR=./downloads
   USE_LOCAL_API=false
   LOCAL_VPARSE_API_BASE=http://localhost:8080
   ```

   If you plan to use a local API, set `USE_LOCAL_API` to `true` and ensure `LOCAL_VPARSE_API_BASE` points to your local API service address.

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

This will build a Docker image named `vparse-mcp` with the tag `latest` based on the Dockerfile.

### 4.2 Run the Container

Run the container using an environment variable file:

```bash
docker run -p 8001:8001 --env-file .env vparse-mcp:latest
```

Alternatively, specify environment variables directly:

```bash
docker run -p 8001:8001 \
  -e VPARSE_API_BASE=https://vparse.net \
  -e VPARSE_API_KEY=your_api_key_here \
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

| Environment Variable | Description | Default Value |
| ------------------------- | -------------------------------------------------------------- | ------------------------- |
| `VPARSE_API_BASE` | Base URL for the VParse remote API | `https://vparse.net` |
| `VPARSE_API_KEY` | VParse API key, required from the official website | - |
| `OUTPUT_DIR` | Path to save converted files | `/app/downloads` |
| `USE_LOCAL_API` | Whether to use a local API for parsing (only for `local_parse_pdf` tool) | `false` |
| `LOCAL_VPARSE_API_BASE` | Base URL for the local API (effective when `USE_LOCAL_API=true`) | `http://localhost:8080` |

In a Docker environment, you can:

- Specify an environment file via `--env-file`.
- Pass variables directly using the `-e` flag.
- Configure variables in the `environment` section of `docker-compose.yml`.
