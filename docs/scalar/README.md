# Scalar API Documentation

This folder hosts a hand-crafted OpenAPI 3.1 specification tailored for the Gemma 3 speech API.
Use [Scalar](https://github.com/scalar/scalar) to render an interactive reference for testers and
QA engineers.

## Preview locally

```bash
# Install the Scalar CLI if it is not already available
npm install --global @scalar/cli

# Launch an interactive preview that watches for file changes
scalar preview docs/scalar/openapi.yaml
```

The CLI serves a documentation site at `http://localhost:9025` by default. Point the preview at a
different server by editing the `servers` block inside `openapi.yaml`.

## Export static documentation

```bash
# Generate a static HTML bundle under docs/scalar/dist
scalar build docs/scalar/openapi.yaml --out docs/scalar/dist
```

The resulting `index.html` and asset bundle can be published to a static hosting provider (GitHub
Pages, Netlify, S3, etc.) so that stakeholders can browse the API contract without running the
FastAPI service locally.

## Keeping the spec fresh

- Update the schema definitions in `openapi.yaml` whenever request/response models change.
- Add new paths for additional REST routes or WebSocket channels. Scalar recognises the
  non-standard `x-scalar-websocket` extension used in this spec to document WebSocket flows.
- Provide concrete examples for new parameters so automated and manual tests have deterministic
  fixtures to work with.
