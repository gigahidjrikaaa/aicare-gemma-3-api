# AICare Speech Playground Frontend

A lightweight Vite + React dashboard for exercising the Gemma 3 text generation, Whisper speech-to-text, Higgs Audio text-to-speech, and dialogue orchestration APIs.

## Prerequisites
- Node.js 18+
- The FastAPI backend from `gemma-3-api/` running locally or accessible via HTTPS
- Optional: Docker (for containerized builds)

## Getting started
```bash
cd frontend
cp .env.example .env              # update with your backend URL/API key
npm install
npm run dev                       # starts Vite on http://localhost:5173
```

The settings drawer within the UI lets you override the API base URL and API key at runtime. These values are stored in `localStorage` so testers can switch between staging and production deployments quickly.

## Available scripts
- `npm run dev` — Hot-reload development server.
- `npm run build` — Type-checks and builds production assets into `dist/`.
- `npm run preview` — Serves the production build locally.
- `npm run lint` — ESLint with React hooks rules & Prettier compatibility.
- `npm run test` — Vitest suite for utilities.

## Deploying the static bundle
1. Build the project: `npm run build`.
2. Upload the contents of `frontend/dist` to any static host (Netlify, Vercel, S3, Cloudflare Pages, etc.).
3. Alternatively, mount the build into the FastAPI app by serving `dist` via `StaticFiles`. Add the following snippet to `gemma-3-api/app/main.py` if you want the backend to serve the SPA:
   ```python
   from fastapi.staticfiles import StaticFiles
   app.mount("/playground", StaticFiles(directory="../frontend/dist", html=True), name="playground")
   ```
4. Ensure the runtime environment exposes `VITE_API_BASE_URL` and `VITE_API_KEY` (if required) via environment variables when building or configure them in the UI at runtime.

## Feature overview
- **Text generation**: Invoke `/v1/generate` and `/v1/generate_stream` with detailed sampling controls and live event logs.
- **Speech-to-text**: Upload audio files, configure Whisper parameters, and view transcript segments with timestamps.
- **Text-to-speech**: Render Higgs Audio responses in blocking and streaming modes with in-browser playback.
- **Dialogue orchestration**: Chain user audio through STT → LLM → TTS, inspecting incremental events and final outputs.
- **Diagnostics**: Global toast notifications, request IDs (when available), and error reporting for quick triage.

## Testing utilities
The project ships with a Vitest harness for the streaming parser utilities. Run `npm run test` to execute the suite. Add additional tests under `src/__tests__/` as new features are introduced.

## CI/CD hints
- Cache `~/.npm` between pipeline runs to speed up installs.
- Run `npm ci` instead of `npm install` in CI for deterministic builds.
- Validate `npm run build` to catch TypeScript or Tailwind regressions before deploying.
