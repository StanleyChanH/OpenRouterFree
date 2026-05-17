# OpenRouterFree - Free Model Proxy Design

## Overview

OpenRouterFree is a lightweight reverse proxy that automatically discovers free AI models from OpenRouter and exposes them through an OpenAI-compatible API. Users point any OpenAI-compatible client at this service and get access to the best free models without manually tracking which models are currently free.

## Architecture

```
Client (OpenAI-compatible) --> FastAPI Service --> OpenRouter API
                                    |
                              +-----------+
                              | Model     | <-- Refreshes every 10 min
                              | Cache     |
                              +-----------+
```

Core flow:
1. Client sends standard OpenAI-format request to `http://localhost:8000/v1/chat/completions`
2. Service inspects the `model` field:
   - Empty or `"auto"` -> replace with the free model having the highest weekly tokens
   - Specific model ID (e.g. `"google/gemma-3-1b-it:free"`) -> use as-is
3. Forward request to `https://openrouter.ai/api/v1/chat/completions` with user's API Key
4. Return OpenRouter's response to the client (streaming and non-streaming)

API Key handling: Client passes OpenRouter API Key via `Authorization: Bearer <key>` header. The service forwards it directly without storing.

## API Endpoints

### POST /v1/chat/completions

Core proxy endpoint. Request/response format is identical to OpenAI Chat Completions API.

Special model field values:
- `"auto"` or omitted -> use the free model with highest weekly tokens
- Specific model ID (e.g. `"nvidia/nemotron-3-super-120b-a12b:free"`) -> use directly
- `"free-random"` -> randomly select from available free models

Supports `stream: true` and `stream: false`. All other parameters (temperature, max_tokens, messages, etc.) are forwarded as-is.

### GET /v1/models

Returns currently cached free model list filtered from OpenRouter.

Response format:
```json
{
  "object": "list",
  "data": [
    {
      "id": "nvidia/nemotron-3-super-120b-a12b:free",
      "object": "model",
      "created": 1234567890,
      "owned_by": "openrouter-free-proxy",
      "context_length": 262144,
      "weekly_tokens": 638000000000
    }
  ]
}
```

Models are sorted by weekly tokens descending. The first entry is the default model.

### GET /v1/models/{model_id}

Returns detailed info for a single free model.

## Model Cache and Selection

### Caching
- On startup: fetch full model list from `https://openrouter.ai/api/v1/models`
- Filter: `pricing.prompt == "0"` and `pricing.completion == "0"`
- Cache in memory, refresh every 10 minutes via background task
- On refresh failure: keep old cache, log warning

### Selection
- Each free model has a usage metric (weekly tokens or similar)
- Model list sorted by weekly tokens descending
- `"auto"` mode selects the top-ranked model (most popular free model)

### Startup behavior
- If OpenRouter API is unreachable at startup, service still starts
- `/v1/models` returns empty list
- `"auto"` model requests return 503 with message "No free models available"

## Project Structure

```
OpenRouterFree/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app entry point, route definitions
│   ├── config.py         # Configuration (port, cache interval, etc.)
│   ├── models.py         # Model cache, filtering, sorting logic
│   └── proxy.py          # Request forwarding, streaming/non-streaming
├── pyproject.toml        # uv project config + dependency declarations
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

### Configuration (environment variables or .env)

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | Service listen port |
| `CACHE_TTL` | `600` | Model cache refresh interval (seconds) |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter API base URL |

### Dependencies (managed by uv)

- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `httpx` - Async HTTP client for request forwarding

## Error Handling

- **OpenRouter returns error**: Forward as-is (status code + error body), never swallow errors
- **Model not found**: If user-specified model is not in free model list, return 404 with suggestion to check `/v1/models`
- **OpenRouter API unreachable**:
  - Cache refresh failure -> keep old cache, log warning
  - Request forwarding failure -> return 502 "OpenRouter service temporarily unavailable"
- **Missing API Key**: No `Authorization` header -> return 401 "OpenRouter API Key required"

## Technology Decisions

- **Language**: Python + FastAPI
- **Package manager**: uv
- **Deployment**: Both direct run (`uv run`) and Docker
- **API Key**: User-provided (passthrough, no storage)
