# OpenRouterFree

Lightweight proxy that auto-discovers free AI models from [OpenRouter](https://openrouter.ai) and exposes them through an OpenAI-compatible API.

## Quick Start

```bash
# Install dependencies
uv sync

# Start the server
uv run uvicorn app.main:app

# Or with custom port
PORT=3000 uv run uvicorn app.main:app --port 3000
```

## Docker

```bash
docker compose up -d
```

## Usage

The API is OpenAI-compatible. Point any OpenAI client at `http://localhost:8000`.

### Chat Completions

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_OPENROUTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

**Model field options:**
- `"auto"` or omitted — use the most popular free model (by weekly tokens)
- `"free-random"` — randomly pick a free model
- Specific model ID (e.g. `"deepseek/deepseek-v4-flash:free"`) — use that model

### List Free Models

```bash
curl http://localhost:8000/v1/models | jq
```

### Get Single Model

```bash
curl http://localhost:8000/v1/models/deepseek/deepseek-v4-flash:free | jq
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | Server port |
| `CACHE_TTL` | `600` | Model cache refresh interval (seconds) |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter API base URL |

## Development

```bash
# Run tests
uv run pytest -v

# Run with auto-reload
uv run uvicorn app.main:app --reload
```
