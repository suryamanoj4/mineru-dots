# Deploying VParse with Docker

VParse provides a convenient Docker deployment method, which helps quickly set up the environment and solve some tricky environment compatibility issues.

## Build Docker Image using Dockerfile

```bash
docker build -t vparse:gpu -f docker/global/Dockerfile .
docker build -t vparse:cpu -f docker/global/Dockerfile.cpu .
```

> [!TIP]
> The [Dockerfile](https://github.com/opendatalab/VParse/blob/master/docker/global/Dockerfile) uses `vllm/vllm-openai:v0.10.1.1` as the base image by default. This version of vLLM v1 engine has limited support for GPU models. 
> This version supports a limited range of GPU models and may only function on Ampere, Ada Lovelace, and Hopper architectures. If you cannot use vLLM for accelerated inference on Volta, Turing, or Blackwell GPUs, you can resolve this issue by changing the base image to `vllm/vllm-openai:v0.11.0`.

## Docker Description

VParse's Docker uses `vllm/vllm-openai` as the base image, so it includes the `vllm` inference acceleration framework and necessary dependencies by default. Therefore, on compatible devices, you can directly use `vllm` to accelerate VLM model inference.

> [!NOTE]
> Requirements for using `vllm` to accelerate VLM model inference:
> 
> - Device must have Volta architecture or later graphics cards with 8GB+ available VRAM.
> - The host machine's graphics driver should support CUDA 12.8 or higher; You can check the driver version using the `nvidia-smi` command.
> - Docker container must have access to the host machine's graphics devices.

## Start Docker Container

```bash
# Example: start an interactive shell from the GPU image
docker run --gpus all \
  --shm-size 32g \
  -p 30000:30000 -p 7860:7860 -p 8000:8000 \
  --ipc=host \
  -it vparse:gpu \
  /bin/bash
```

After executing this command, you will enter the Docker container's interactive terminal with some ports mapped for potential services. You can directly run VParse-related commands within the container to use VParse's features.
You can also directly start VParse services by replacing `/bin/bash` with service startup commands. For detailed instructions, please refer to the [Start the service via command](https://opendatalab.github.io/VParse/usage/quick_usage/#advanced-usage-via-api-webui-http-clientserver).

## Start Services Directly with Docker Compose

We provide a [compose.yaml](https://github.com/opendatalab/VParse/blob/master/docker/compose.yaml) file that you can use to quickly start VParse services.

```bash
# Run from the repository root
cd /path/to/VParse
```

>[!NOTE]
>
- The Docker Compose setup is organized around three hardware/runtime profiles: `cpu`, `gpu`, and `hybrid`.
- The Compose file in this branch is focused on Gradio deployment profiles. The previous Compose services for the OpenAI-compatible server and API are not included here.
- Start only one profile at a time because the `gpu` and `hybrid` profiles both rely on local GPU-backed inference.
- The Compose services build from the local checkout, so your branch changes are included in the image.
- Models are never downloaded during `docker build`; the API container prepares the required models on first startup instead.
- Model caches and the generated `mineru.json` are persisted in Docker volumes, so the first download is reused across container restarts and recreations.
- If you run commands from the repository root, keep passing `-f docker/compose.yaml` to follow-up commands such as `ps`, `logs`, `down`, and `restart`. Alternatively, `cd docker` first and then run `docker compose ...`.

---

### Start CPU mode

Use this on machines without an NVIDIA GPU. The Gradio UI will expose only the `pipeline` backend.

```bash
docker compose -f docker/compose.yaml --profile cpu up -d
```

To stop the CPU profile:

```bash
docker compose -f docker/compose.yaml --profile cpu down
```

To rebuild the image and start the CPU profile again:

```bash
docker compose -f docker/compose.yaml --profile cpu up -d --build
```

To inspect the running CPU container:

```bash
docker compose -f docker/compose.yaml ps
docker compose -f docker/compose.yaml logs -f vparse-gradio-cpu
```

Open `http://<server_ip>:7860` in your browser.
The first `docker compose up` may take longer because the API container downloads pipeline models into the shared cache volume before it starts serving requests. After that, restarts reuse the same volume.

### Start GPU mode

Use this on machines with an NVIDIA GPU when you want VLM-based parsing. The Gradio UI will expose only the `vlm-auto-engine` backend.

```bash
docker compose -f docker/compose.yaml --profile gpu up -d
```

To stop the GPU profile:

```bash
docker compose -f docker/compose.yaml --profile gpu down
```

To rebuild the image and start the GPU profile again:

```bash
docker compose -f docker/compose.yaml --profile gpu up -d --build
```

To inspect the running GPU container:

```bash
docker compose -f docker/compose.yaml ps
docker compose -f docker/compose.yaml logs -f vparse-gradio-gpu
```

Open `http://<server_ip>:7860` in your browser.
The first `docker compose up` may take longer because the API container downloads the VLM model into the shared cache volume before it starts serving requests.

### Start Hybrid mode

Use this on machines with an NVIDIA GPU when you want the hybrid parser. The Gradio UI will expose only the `hybrid-auto-engine` backend.

```bash
docker compose -f docker/compose.yaml --profile hybrid up -d
```

Open `http://<server_ip>:7860` in your browser.
The first `docker compose up` may take longer because the API container downloads both pipeline and VLM models into the shared cache volume before it starts serving requests.
