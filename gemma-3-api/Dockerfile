# Dockerfile for GGUF / llama-cpp-python
# This version includes all necessary build tools and correct flags for compilation.

FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_NO_CACHE_DIR=true

# Install Python and all necessary build tools (git, cmake, ninja)
RUN apt-get update && \
    apt-get install -y python3.11 python3-pip git cmake ninja-build && \
    rm -rf /var/lib/apt/lists/*
    
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Set the library path to include CUDA stubs for the linker during build.
# This is crucial for resolving linker errors.
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64/stubs

# Set build arguments for llama-cpp-python to enable CUDA support using the new flag.
ARG CMAKE_ARGS="-DGGML_CUDA=on"
ENV FORCE_CMAKE=1

# Create a non-root user with the same IDs as the host user to prevent permission errors.
ARG UID=1000
ARG GID=1000
RUN groupadd -g $GID appuser && useradd -m -s /bin/bash -u $UID -g $GID appuser
    
USER appuser
WORKDIR /home/appuser/app

COPY --chown=appuser:appuser requirements.txt .

# Install python dependencies from requirements.txt
RUN pip3 install -r requirements.txt

COPY --chown=appuser:appuser ./app .

EXPOSE 6666

# Use the absolute path to uvicorn to ensure it's found.
CMD ["/home/appuser/.local/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "6666"]
