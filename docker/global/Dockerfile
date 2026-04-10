# Use the official vllm image for gpu with Ampere、Ada Lovelace、Hopper architecture (8.0 <= Compute Capability <= 9.0)
# Compute Capability version query (https://developer.nvidia.com/cuda-gpus)
# only support x86_64 architecture
FROM vllm/vllm-openai:v0.10.1.1

# Use the official vllm image for gpu with Volta、Turing、Blackwell architecture (7.0 < Compute Capability < 8.0 or Compute Capability >= 10.0)
# support x86_64 architecture and ARM(AArch64) architecture
# FROM vllm/vllm-openai:v0.11.0

# Install libgl for opencv support & Noto fonts for Chinese characters
RUN apt-get update && \
    apt-get install -y \
        fonts-noto-core \
        fonts-noto-cjk \
        fontconfig \
        libglib2.0-0 \
        libgl1 && \
    fc-cache -fv && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

# Install this branch from local source instead of pulling MinerU from PyPI.
RUN python3 -m pip install -U pip --break-system-packages && \
    python3 -m pip install '.[core,vllm]' --break-system-packages && \
    python3 -m pip cache purge

ENTRYPOINT ["/bin/bash", "-c", "exec \"$@\"", "--"]
