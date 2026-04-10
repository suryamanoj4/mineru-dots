# Deploying MinerU with Docker

MinerU provides a convenient Docker deployment method, which helps quickly set up the environment and solve some tricky environment compatibility issues.

## Build Docker Image using Dockerfile

```bash
docker build -t mineru:gpu -f docker/global/Dockerfile .
docker build -t mineru:cpu -f docker/global/Dockerfile.cpu .
```

> [!TIP]
> The [Dockerfile](https://github.com/opendatalab/MinerU/blob/master/docker/global/Dockerfile) uses `vllm/vllm-openai:v0.10.1.1` as the base image by default. This version of vLLM v1 engine has limited support for GPU models. 
> This version supports a limited range of GPU models and may only function on Ampere, Ada Lovelace, and Hopper architectures. If you cannot use vLLM for accelerated inference on Volta, Turing, or Blackwell GPUs, you can resolve this issue by changing the base image to `vllm/vllm-openai:v0.11.0`.

## Docker Description

MinerU's Docker uses `vllm/vllm-openai` as the base image, so it includes the `vllm` inference acceleration framework and necessary dependencies by default. Therefore, on compatible devices, you can directly use `vllm` to accelerate VLM model inference.

> [!NOTE]
> Requirements for using `vllm` to accelerate VLM model inference:
> 
> - Device must have Volta architecture or later graphics cards with 8GB+ available VRAM.
> - The host machine's graphics driver should support CUDA 12.8 or higher; You can check the driver version using the `nvidia-smi` command.
> - Docker container must have access to the host machine's graphics devices.

## Start Docker Container

```bash
docker run --gpus all \
  --shm-size 32g \
  -p 30000:30000 -p 7860:7860 -p 8000:8000 \
  --ipc=host \
  -it mineru:latest \
  /bin/bash
```

After executing this command, you will enter the Docker container's interactive terminal with some ports mapped for potential services. You can directly run MinerU-related commands within the container to use MinerU's features.
You can also directly start MinerU services by replacing `/bin/bash` with service startup commands. For detailed instructions, please refer to the [Start the service via command](https://opendatalab.github.io/MinerU/usage/quick_usage/#advanced-usage-via-api-webui-http-clientserver).

## Start Services Directly with Docker Compose

We provide a [compose.yaml](https://github.com/opendatalab/MinerU/blob/master/docker/compose.yaml) file that you can use to quickly start MinerU services.

```bash
# Run from the repository root
cd /path/to/MinerU
```

>[!NOTE]
>
- The Docker Compose setup is organized around three hardware/runtime profiles: `cpu`, `gpu`, and `hybrid`.
- Start only one profile at a time because the `gpu` and `hybrid` profiles both rely on local GPU-backed inference.
- The Compose services build from the local checkout, so your branch changes are included in the image.
- Models are downloaded on demand at runtime instead of during `docker build`, which keeps image builds much faster.
- Model caches are persisted in Docker volumes, so the first download is reused across container restarts.

---

### Start CPU mode

Use this on machines without an NVIDIA GPU. The Gradio UI will expose only the `pipeline` backend.

```bash
docker compose -f docker/compose.yaml --profile cpu up -d
```

Open `http://<server_ip>:7860` in your browser.
The first container startup may take longer because pipeline models are prepared before Gradio starts. After that, requests use the persistent cache volume.

### Start GPU mode

Use this on machines with an NVIDIA GPU when you want VLM-based parsing. The Gradio UI will expose only the `vlm-auto-engine` backend.

```bash
docker compose -f docker/compose.yaml --profile gpu up -d
```

Open `http://<server_ip>:7860` in your browser.
The first parse request may take longer because VLM models will be downloaded into the persistent cache volume.

### Start Hybrid mode

Use this on machines with an NVIDIA GPU when you want the hybrid parser. The Gradio UI will expose only the `hybrid-auto-engine` backend.

```bash
docker compose -f docker/compose.yaml --profile hybrid up -d
```

Open `http://<server_ip>:7860` in your browser.
The first parse request may take longer because required models will be downloaded into the persistent cache volume.
