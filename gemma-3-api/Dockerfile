# Stage 1: Builder
FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

# Install Python and build essentials
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3.11 python3-pip python3.11-venv git cmake ninja-build && \
    rm -rf /var/lib/apt/lists/*

# Create and activate a virtual environment
RUN python3.11 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Check for pre-built wheels
RUN pip index versions llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124/

# Set environment variables to compile llama-cpp-python with CUDA support.
ENV CMAKE_ARGS="-DGGML_CUDA=on"
ENV FORCE_CMAKE=1

# Install dependencies from requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ==================================================================
# Stage 2: Final Runtime Stage
# ==================================================================
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

# Create a non-root user for security
ARG UID=1000
ARG GID=1000
RUN groupadd -g $GID appuser && useradd --create-home --no-log-init -u $UID -g $GID appuser
WORKDIR /home/appuser/app

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --chown=appuser:appuser ./app .

USER appuser

# Set the PATH to use the Python from our virtual environment
ENV PATH="/opt/venv/bin:$PATH"

EXPOSE 6666

# Command to run your application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "6666"]