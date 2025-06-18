# DevOps Guide: Gemma 3 API Service

**Last Updated:** June 17, 2025

This document provides all the necessary commands and operational procedures for building, deploying, managing, and testing the `gemma-3-api` service. It is intended for developers and system administrators responsible for the service's lifecycle on the `aiserv` host machine.

---

## 1. Host Machine Prerequisites

This service is designed to run within a Docker container but relies on host-level hardware support. Before you begin, ensure the following are installed and correctly configured on the host machine.

1.  **NVIDIA Drivers:** The host must have the correct proprietary NVIDIA drivers installed.
    * **Verification:**
        ```bash
        nvidia-smi
        ```
        This command should successfully display information about the installed GPUs (Tesla P40, Quadro M4000) without errors.

2.  **Docker Engine:** The containerization platform.
    * **Verification:**
        ```bash
        docker --version
        ```

3.  **NVIDIA Container Toolkit:** The bridge that allows Docker containers to access the host's GPUs.
    * **Verification:** This command runs a temporary container and asks it to execute `nvidia-smi`. A successful run confirms the toolkit is correctly configured.
        ```bash
        sudo docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
        ```

---

## 2. Building the Docker Image

The entire application, including all dependencies, is packaged into a Docker image named `gemma-3-api`. Before running the service for the first time, or after any changes to the source code (`app/main.py`, `Dockerfile`, `requirements.txt`), you must build (or rebuild) the image.

**Build Command:**

This command must be run from the project's root directory (`~/Gemma-Finetune/gemma-3-api`). It is crucial to pass the current user's ID and group ID as build arguments to prevent file permission errors when mounting the Hugging Face cache.

```bash
docker build \
  --build-arg UID=$(id -u) \
  --build-arg GID=$(id -g) \
  -t gemma-3-api .
```

3. Running the Service
There are two primary ways to run the container: interactively for debugging or detached as a persistent background service for production.

A. Running in Interactive Mode (for Development & Debugging)
This mode is ideal for testing changes or troubleshooting, as all application logs are printed directly to your terminal. The container is automatically removed when you stop it (Ctrl+C), ensuring a clean state for the next run.

```bash
docker run --rm -it \
  --gpus all \
  -p 6666:6666 \
  -v ~/.cache/huggingface:/home/appuser/.cache/huggingface \
  -e HUGGING_FACE_HUB_TOKEN=$(cat ~/.cache/huggingface/token) \
  --name gemma_service_debug \
  gemma-3-api
```

B. Running in Production Mode (Background Service)
This is the standard command for deploying the service. It runs the container in the background and sets a restart policy to ensure it comes back online automatically if it ever crashes or the server reboots.

```bash
docker run \
    -d \
    --restart always \
    --gpus all \
    -p 6666:6666 \
    -v ~/.cache/huggingface:/home/appuser/.cache/huggingface \
    -e HUGGING_FACE_HUB_TOKEN=$(cat ~/.cache/huggingface/token) \
    --name gemma_service \
    gemma-3-api
```

Key Flags:

-d or --detach: Runs the container in the background.

--restart always: A powerful policy that makes the container a persistent service.

4. Managing the Live Service
Once the service is running in detached mode, use these standard Docker commands to manage its lifecycle.

Check Status of Running Containers:

```bash
docker ps
```

View Service Logs (Most Important):
This is how you monitor the API server's output in the background.

```bash
# View a snapshot of the most recent logs
docker logs gemma_service

# Follow the logs live (similar to `tail -f`). Press Ctrl+C to exit.
docker logs -f gemma_service
```

Stop the Service:

```bash
docker stop gemma_service

Start a Stopped Service:

docker start gemma_service
```

Permanently Remove the Service:
You must stop the container before you can remove it.

```bash
docker stop gemma_service
docker rm gemma_service
```

5. Testing the API
With the service running, you can test its endpoints from the host machine's command line using curl.

A. Health Check
This is the quickest way to verify that the API server is up and responsive.

```bash
curl http://localhost:6666/health
```

Expected Output: {"status":"ok"}

B. Full Inference Test
This sends a real prompt to the model to verify the entire end-to-end functionality.

```bash
curl -X POST http://localhost:6666/v1/generate \
-H "Content-Type: application/json" \
-d '{
  "prompt": "What is the significance of the GGUF model format in the local LLM community?",
  "max_tokens": 256
}'
```

Expected Output: A JSON object containing the model's generated text, for example: {"generated_text":"The GGUF (GPT-Generated Unified Format) model format is highly significant..."}.

6. Standard Update Procedure
To deploy new code or dependency changes, follow this three-step "rebuild and replace" process for a clean update.

Build the new image version with your changes:

```bash
docker build --build-arg UID=$(id -u) --build-arg GID=$(id -g) -t gemma-3-api .
```

Stop and remove the old running container:

```bash
docker stop gemma_service
docker rm gemma_service
```

Start a new container using the freshly built image:
(Use the production run command from Section 3B)

```bash
docker run -d --restart always --gpus all -p 6666:6666 ... gemma-3-api
```
