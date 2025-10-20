# Gemma 3 Speech API

A FastAPI application that serves the Gemma 3 language model with support for text generation, OpenAI Whisper-based speech-to-text, and OpenAudio-S1-mini text-to-speech. The service exposes REST and WebSocket interfaces and is designed to run inside a CUDA-enabled container with optional local Whisper inference.

## Features

- **Text generation** via llama.cpp-backed Gemma 3 checkpoints with synchronous and streaming APIs.
- **Speech-to-text** using OpenAI Whisper (remote API by default, optional local inference when the `openai-whisper` package and FFmpeg are available).
- **Text-to-speech** through the OpenAudio-S1-mini deployment with blocking and streaming responses.
- **Speech dialogue** endpoint that combines Whisper, Gemma, and OpenAudio with optional streaming JSON events.
- **API key enforcement** for REST and WebSocket routes with configurable header names and key rotation support.
- **Configurable rate limiting** for REST and WebSocket clients to protect shared deployments.
- **Structured logging & Prometheus metrics** including request IDs, latency histograms, and a `/metrics` scrape endpoint.
- Centralised configuration through environment variables using `pydantic-settings`.
- Docker and Docker Compose definitions optimised for GPU execution.

## Prerequisites

- NVIDIA GPU with recent CUDA drivers (the provided Dockerfile targets CUDA 12.4).
- Docker Engine and Docker Compose v2 for container-based deployments.
- Python 3.11+ if running the application outside containers.

The Docker images install FFmpeg and libsndfile to support Whisper audio processing. When developing locally you should install these packages manually (`sudo apt install ffmpeg libsndfile1` on Debian/Ubuntu).

## Installing Python dependencies

```bash
cd gemma-3-api
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

The requirements include `openai-whisper` for optional on-device transcription and `soundfile` for reading PCM payloads. PyTorch is pulled automatically by the Whisper package.

## Configuring OpenAudio-S1-mini

1. Download the OpenAudio-S1-mini checkpoint from the [Fish Audio release](https://huggingface.co/fishaudio/OpenAudio-S1-mini) and place it in a directory accessible to the API (the Compose file mounts `./openaudio-checkpoints`).
2. Start the OpenAudio API server by running `python -m tools.api_server --model OpenAudio-S1-mini --compile --host 0.0.0.0 --port 8080` inside the upstream repository, or reuse the optional `openaudio` service defined in `docker-compose.yml`.
3. Set `OPENAUDIO_API_BASE` to the reachable base URL (defaults to `http://openaudio:8080`) and provide an API key via `OPENAUDIO_API_KEY` if your deployment enforces authentication.

The API expects the `/v1/tts` route exposed by the upstream server. Streaming synthesis requires the deployment to support HTTP chunked responses.

## Configuring Whisper

- **Remote mode (default):** provide an OpenAI API key via `OPENAI_API_KEY`. Optionally customise `OPENAI_API_BASE` to target Azure/OpenAI-compatible gateways and `OPENAI_WHISPER_MODEL` to pick a different transcription model (e.g. `gpt-4o-mini-transcribe`).
- **Local mode:** set `ENABLE_LOCAL_WHISPER=true`. The container image already installs `openai-whisper`, FFmpeg, and libsndfile. You can change the checkpoint with `LOCAL_WHISPER_MODEL` (e.g. `medium`, `large-v3`). Local inference downloads models to `~/.cache/whisper`; mount a persistent volume if you want to reuse them across runs.

## Environment variables

| Variable | Description |
| --- | --- |
| `HUGGING_FACE_HUB_TOKEN` | Optional token for downloading private Gemma checkpoints. |
| `OPENAI_API_KEY` | API key used for remote Whisper transcription. Required unless local mode is enabled. |
| `OPENAI_API_BASE` | Override for the OpenAI API base URL. Useful for Azure/OpenAI-compatible proxies. |
| `OPENAI_TIMEOUT_SECONDS` | Network timeout applied to Whisper requests. |
| `OPENAI_WHISPER_MODEL` | Default Whisper model identifier (remote mode). |
| `OPENAI_WHISPER_RESPONSE_FORMAT` | Response format requested from Whisper (e.g. `verbose_json`). |
| `ENABLE_LOCAL_WHISPER` | Toggle on-device Whisper inference. Requires FFmpeg and the `openai-whisper` package. |
| `LOCAL_WHISPER_MODEL` | Whisper checkpoint to load in local mode. |
| `OPENAUDIO_API_KEY` | Authentication token forwarded to OpenAudio deployments. |
| `OPENAUDIO_API_BASE` | Base URL of the OpenAudio API (e.g. `http://openaudio:8080`). |
| `OPENAUDIO_TTS_PATH` | Speech synthesis path appended to the base URL (defaults to `/v1/tts`). |
| `OPENAUDIO_DEFAULT_FORMAT` | Default output format (e.g. `wav`, `mp3`). |
| `OPENAUDIO_DEFAULT_REFERENCE_ID` | Default reference identifier forwarded to OpenAudio when none is supplied. |
| `OPENAUDIO_DEFAULT_NORMALIZE` | Whether to request loudness normalisation by default. |
| `OPENAUDIO_TIMEOUT_SECONDS` | Network timeout applied to OpenAudio synthesis requests. |
| `OPENAUDIO_MAX_RETRIES` | Number of retry attempts for recoverable OpenAudio errors. |
| `LOG_LEVEL` | Logging level used for the application (e.g. `DEBUG`, `INFO`). |
| `REQUEST_ID_HEADER` | Header propagated on responses containing the per-request identifier. |
| `API_KEY_ENABLED` | Set to `true` to require API keys for REST and WebSocket endpoints. |
| `API_KEY_HEADER_NAME` | Header inspected for API keys (defaults to `X-API-Key`). |
| `API_KEYS` | Comma-separated list of valid API keys (used when `API_KEY_ENABLED=true`). |
| `RATE_LIMIT_ENABLED` | Enable global rate limiting when set to `true`. |
| `RATE_LIMIT_REQUESTS` | Number of allowed requests per window (default `120`). |
| `RATE_LIMIT_WINDOW_SECONDS` | Length of the sliding window in seconds (default `60`). |
| `RATE_LIMIT_BURST_MULTIPLIER` | Multiplier applied to the base allowance to permit short bursts (default `1.0`). |
| `LLM_*` vars | Advanced llama.cpp configuration (see `app/config/settings.py`). |

## Running with Docker

Build and launch the service:

```bash
cd gemma-3-api
docker compose up --build
```

The Compose file exposes port `6666` and forwards speech configuration variables. To enable local Whisper and persist downloaded checkpoints:

```bash
ENABLE_LOCAL_WHISPER=true \
LOCAL_WHISPER_MODEL=large-v3 \
WHISPER_CACHE=$HOME/.cache/whisper \
docker compose up --build
```

Then add the following volume mapping inside `docker-compose.yml` if you want cache persistence:

```yaml
    volumes:
      - ~/.cache/huggingface:/home/appuser/.cache/huggingface
      - ${WHISPER_CACHE:-~/.cache/whisper}:/home/appuser/.cache/whisper
```

The Compose file already provisions an `openaudio` service based on the upstream Fish Audio image. Point `OPENAUDIO_API_BASE` at `http://openaudio:8080` (the default) or adjust the environment variables to match your custom deployment.

## Running locally without Docker

```bash
export OPENAI_API_KEY=sk-...
uvicorn app.main:app --host 0.0.0.0 --port 6666
```

GPU acceleration for llama.cpp requires the necessary CUDA libraries to be available on the host.

## API overview

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/v1/generate` | Synchronous text generation request. |
| `POST` | `/v1/generate_stream` | Streaming text generation over HTTP chunked responses. |
| `WS` | `/v1/generate_ws` | Bidirectional WebSocket text generation. |
| `POST` | `/v1/speech-to-text` | Transcribe uploaded audio via Whisper. |
| `POST` | `/v1/text-to-speech` | Convert text to speech using OpenAudio. |
| `POST` | `/v1/dialogue` | Run end-to-end speech dialogue (Whisper → Gemma → OpenAudio). |
| `WS` | `/v1/speech-to-text/ws` | WebSocket transcription using base64 audio payloads. |
| `WS` | `/v1/text-to-speech/ws` | WebSocket speech synthesis with streamed audio chunks. |
| `GET` | `/metrics` | Prometheus metrics (latency histograms, error counters). |

Interactive API docs are available at `http://localhost:6666/docs` once the server is running.

### Dialogue streaming format

When `stream_audio=true`, `/v1/dialogue` responds with newline-delimited JSON objects. The sequence of events is:

1. `{"event": "metadata"}` — audio format, MIME type, sample rate, and optional `reference_id` information.
2. `{"event": "transcript"}` — Whisper transcript payload matching `SpeechTranscriptionResponse`.
3. `{"event": "assistant_text"}` — Gemma-generated assistant reply.
4. One or more `{"event": "audio_chunk"}` objects containing base64-encoded OpenAudio samples.
5. A terminal `{"event": "done"}` message.

Clients should parse each line independently to reconstruct the dialogue response.

## Health check

The service exposes `/health` for container orchestration probes.

## Observability & security

- Requests receive a `X-Request-ID` header (configurable via `REQUEST_ID_HEADER`) that is propagated in structured logs.
- Request/response latency, error counts, and orchestration timing metrics are exported to Prometheus under `/metrics`.
- External integrations (Whisper, OpenAudio, Gemma) contribute latency histograms, making it easy to identify bottlenecks.
- Enable API key protection by setting `API_KEY_ENABLED=true` and providing a comma-separated list in `API_KEYS`. WebSocket clients must include the key header during the handshake.
- Activate rate limiting with `RATE_LIMIT_ENABLED=true` to apply a shared token bucket. The limiter prioritises API keys (each key has its own bucket) and falls back to the client IP when unauthenticated. Rejections surface as HTTP 429 responses (or WebSocket close code 4429) and increment the Prometheus metric `app_rate_limit_rejections_total` labelled by scope.

### Rate limiting examples

The defaults permit 120 requests per minute with no burst. To allow up to 5× momentary bursts while keeping the same sustained throughput, set:

```bash
RATE_LIMIT_ENABLED=true \
RATE_LIMIT_REQUESTS=120 \
RATE_LIMIT_WINDOW_SECONDS=60 \
RATE_LIMIT_BURST_MULTIPLIER=5
```

`Retry-After` headers indicate how many seconds a client should wait before retrying. Because rate limiting is enforced for WebSocket handshakes as well, long-lived streaming sessions should be multiplexed rather than constantly reconnecting.

## Testing

Run the automated unit tests, including coverage for the conversation orchestrator and security helpers:

```bash
pytest
```

For quick syntax validation without running dependencies you can still execute:

```bash
python -m compileall app
```
