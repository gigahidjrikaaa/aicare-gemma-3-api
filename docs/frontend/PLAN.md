# Frontend Implementation Plan

## Goals
- Provide a browser-based harness that exercises the backend text generation, speech-to-text, text-to-speech, and dialogue pipelines individually or in sequence.
- Keep the project lightweight, fully documented, and easily deployable alongside the FastAPI backend (local dev & static hosting).

## Stack & Tooling
- **Vite + React + TypeScript** for a modern yet minimal SPA scaffold.
- **Tailwind CSS** for rapid layout/utility styling without heavy component dependencies.
- **TanStack Query** for request lifecycle management on REST endpoints.
- Custom hooks for streaming NDJSON/audio over `fetch` and WebSockets.
- Build output served as static assets (Vite `npm run build`) compatible with any static host or the FastAPI backend via `StaticFiles` (future option).

## Key Features
1. **Environment configuration**
   - `.env.example` with `VITE_API_BASE_URL`, `VITE_API_KEY`, `VITE_STREAMING_MODE`.
   - Runtime settings drawer allowing testers to update base URL/API key without rebuild (stored in localStorage).

2. **Navigation layout**
   - Tabs for "Text Generation", "Speech-to-Text", "Text-to-Speech", and "Dialogue".
   - Each tab contains form controls mirroring backend schemas, result viewers, and raw JSON toggles.

3. **API client utilities**
   - Centralized `apiClient.ts` to apply headers, attach API key, handle 401/429, and emit request IDs.
   - `useNdjsonStream` helper to parse incremental responses (token streams, audio chunks).

4. **Panels**
   - **GenerationPanel**: prompt textarea, sampling sliders, run buttons for sync and streaming, incremental token display.
   - **TranscriptionPanel**: audio file picker, advanced options, transcript + timestamps view.
   - **SynthesisPanel**: text entry, voice/model selection, streaming toggle, audio playback & download.
   - **DialoguePanel**: upload audio, optional instruction overrides, streaming event log, aggregated results.
   - Each panel exposes "Send to next stage" actions to chain outputs (e.g., transcript -> prompt -> speech).

5. **Streaming handling**
   - NDJSON parser appends events to state; audio chunks accumulate into `Blob` for playback.
   - WebSocket hook for optional low-latency tests; UI displays connection state and message log.

6. **Diagnostics**
   - Global toast/alert system for errors, show status codes and request IDs.
   - Latency timers per request and final summary row.

## Deployment & DX
- `npm run dev` for local development.
- `npm run build` + `npm run preview` for production validation.
- Document integration steps in `frontend/README.md` and top-level README mention.
- Provide GitHub Actions placeholder (future) and instructions for static hosting (e.g., Vercel, Netlify, or FastAPI static mount).

## Testing
- Include `npm run lint` using ESLint/TypeScript defaults.
- Add basic Vitest test for NDJSON parser utility.

## Deliverables for this phase
- `frontend/` project directory with source, config, lint/test scripts.
- UI implementing four panels with functional REST requests and streaming parsing.
- Documentation updates for setup & deployment.
- Minimal unit test(s) + successful build command execution.
