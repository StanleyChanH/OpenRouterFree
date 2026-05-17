# OpenRouterFree Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a lightweight FastAPI proxy that auto-discovers free OpenRouter models (sorted by weekly token usage) and exposes them via an OpenAI-compatible API.

**Architecture:** Reverse proxy pattern. Service fetches model list from OpenRouter API (`?order=top-weekly`), filters free models, and stores them in an in-memory cache refreshed every 10 minutes. Client requests are forwarded to OpenRouter with the model field resolved (auto → top free model, specific ID → as-is, free-random → random pick). Supports both streaming and non-streaming responses.

**Tech Stack:** Python 3.12+, FastAPI, uvicorn, httpx, uv (package manager), Docker

---

## File Structure

| File | Responsibility |
|------|---------------|
| `pyproject.toml` | Project metadata and dependencies (uv) |
| `app/__init__.py` | Package marker |
| `app/config.py` | Environment variable configuration |
| `app/models.py` | FreeModel dataclass, ModelCache (fetch, filter, cache, refresh) |
| `app/proxy.py` | Model resolution, request forwarding (streaming + non-streaming) |
| `app/main.py` | FastAPI app with lifespan, route handlers |
| `tests/__init__.py` | Package marker |
| `tests/conftest.py` | Shared test fixtures |
| `tests/test_models.py` | ModelCache unit tests |
| `tests/test_proxy.py` | Proxy resolution tests |
| `tests/test_api.py` | API route integration tests |
| `Dockerfile` | Multi-stage Docker build |
| `docker-compose.yml` | Docker Compose config |
| `.env.example` | Example environment variables |
| `README.md` | Usage documentation |

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `app/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Initialize uv project**

Run:
```bash
cd E:/GitProjects/OpenRouterFree
uv init --name openrouter-free --python 3.12
```

- [ ] **Step 2: Overwrite pyproject.toml with correct dependencies**

```toml
[project]
name = "openrouter-free"
version = "0.1.0"
description = "Proxy for OpenRouter free AI models with OpenAI-compatible API"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "httpx>=0.27.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 3: Install dependencies**

Run:
```bash
uv sync
```
Expected: Dependencies installed, `uv.lock` created.

- [ ] **Step 4: Create package directories**

```bash
mkdir -p app tests
```

Create `app/__init__.py` (empty file).
Create `tests/__init__.py` (empty file).

- [ ] **Step 5: Verify setup**

Run:
```bash
uv run python -c "import fastapi; import httpx; print('OK')"
```
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock app/ tests/ .python-version
git commit -m "chore: initialize project with uv, fastapi, httpx"
```

---

### Task 2: Config Module

**Files:**
- Create: `app/config.py`

- [ ] **Step 1: Write config module**

Create `app/config.py`:

```python
import os

PORT = int(os.environ.get("PORT", "8000"))
CACHE_TTL = int(os.environ.get("CACHE_TTL", "600"))
OPENROUTER_BASE_URL = os.environ.get(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
)
```

- [ ] **Step 2: Verify config loads**

Run:
```bash
uv run python -c "from app.config import PORT, CACHE_TTL, OPENROUTER_BASE_URL; print(f'PORT={PORT} CACHE_TTL={CACHE_TTL}')"
```
Expected: `PORT=8000 CACHE_TTL=600`

- [ ] **Step 3: Commit**

```bash
git add app/config.py
git commit -m "feat: add configuration module with env var support"
```

---

### Task 3: Test Fixtures

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Write shared test fixtures**

Create `tests/conftest.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch

from app.models import FreeModel, model_cache


TEST_MODELS = [
    FreeModel(id="test/model-a:free", name="Model A", context_length=8192, created=1000),
    FreeModel(id="test/model-b:free", name="Model B", context_length=32768, created=2000),
]


@pytest.fixture
def populated_cache():
    model_cache._models = list(TEST_MODELS)
    yield model_cache
    model_cache._models = []


@pytest.fixture
def mock_lifespan():
    with patch.object(model_cache, "start", new_callable=AsyncMock), \
         patch.object(model_cache, "stop", new_callable=AsyncMock):
        model_cache._models = list(TEST_MODELS)
        yield
        model_cache._models = []


@pytest.fixture
async def api_client(mock_lifespan):
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
```

- [ ] **Step 2: Verify test infrastructure**

Run:
```bash
uv run pytest --collect-only
```
Expected: No errors (0 tests collected is fine at this stage).

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add shared test fixtures"
```

---

### Task 4: Model Cache

**Files:**
- Create: `tests/test_models.py`
- Create: `app/models.py`

- [ ] **Step 1: Write failing tests for model parsing**

Create `tests/test_models.py`:

```python
from app.models import FreeModel, ModelCache


class TestParseFreeModels:
    def test_filters_free_models(self):
        raw = [
            {
                "id": "free/model:free",
                "name": "Free",
                "context_length": 8192,
                "created": 1000,
                "pricing": {"prompt": "0", "completion": "0"},
            },
            {
                "id": "paid/model",
                "name": "Paid",
                "context_length": 8192,
                "created": 2000,
                "pricing": {"prompt": "0.001", "completion": "0.002"},
            },
        ]
        result = ModelCache._parse_free_models(raw)
        assert len(result) == 1
        assert result[0].id == "free/model:free"

    def test_preserves_api_order(self):
        raw = [
            {
                "id": "model-a:free",
                "name": "A",
                "context_length": 8192,
                "created": 1000,
                "pricing": {"prompt": "0", "completion": "0"},
            },
            {
                "id": "model-b:free",
                "name": "B",
                "context_length": 32768,
                "created": 2000,
                "pricing": {"prompt": "0", "completion": "0"},
            },
        ]
        result = ModelCache._parse_free_models(raw)
        assert [m.id for m in result] == ["model-a:free", "model-b:free"]

    def test_excludes_partial_free(self):
        raw = [
            {
                "id": "partial:free",
                "name": "Partial",
                "context_length": 8192,
                "created": 1000,
                "pricing": {"prompt": "0", "completion": "0.001"},
            },
        ]
        result = ModelCache._parse_free_models(raw)
        assert len(result) == 0

    def test_excludes_no_pricing(self):
        raw = [{"id": "no-price", "name": "No Price", "context_length": 8192, "created": 1000}]
        result = ModelCache._parse_free_models(raw)
        assert len(result) == 0


class TestModelCacheAccess:
    def test_default_model_returns_first(self, populated_cache):
        assert populated_cache.default_model.id == "test/model-a:free"

    def test_default_model_empty_cache(self):
        cache = ModelCache()
        assert cache.default_model is None

    def test_get_model_found(self, populated_cache):
        m = populated_cache.get_model("test/model-b:free")
        assert m is not None
        assert m.name == "Model B"

    def test_get_model_not_found(self, populated_cache):
        assert populated_cache.get_model("nonexistent") is None

    def test_models_returns_copy(self, populated_cache):
        models = populated_cache.models
        assert len(models) == 2
        models.clear()
        assert len(populated_cache.models) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
uv run pytest tests/test_models.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models'`

- [ ] **Step 3: Write ModelCache implementation**

Create `app/models.py`:

```python
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import CACHE_TTL, OPENROUTER_BASE_URL

logger = logging.getLogger(__name__)


@dataclass
class FreeModel:
    id: str
    name: str
    context_length: int
    created: int
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


class ModelCache:
    def __init__(self) -> None:
        self._models: list[FreeModel] = []
        self._client: httpx.AsyncClient | None = None
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)
        await self.refresh()
        self._task = asyncio.create_task(self._periodic_refresh())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        if self._client:
            await self._client.aclose()

    async def refresh(self) -> None:
        try:
            resp = await self._client.get(
                f"{OPENROUTER_BASE_URL}/models",
                params={"order": "top-weekly"},
            )
            resp.raise_for_status()
            raw_models = resp.json().get("data", [])
            self._models = self._parse_free_models(raw_models)
            logger.info("Refreshed %d free models", len(self._models))
        except Exception:
            logger.warning("Failed to refresh models", exc_info=True)

    @staticmethod
    def _parse_free_models(models: list[dict]) -> list[FreeModel]:
        free: list[FreeModel] = []
        for m in models:
            pricing = m.get("pricing", {})
            if pricing.get("prompt") == "0" and pricing.get("completion") == "0":
                free.append(
                    FreeModel(
                        id=m["id"],
                        name=m.get("name", m["id"]),
                        context_length=m.get("context_length", 4096),
                        created=m.get("created", 0),
                        raw=m,
                    )
                )
        return free

    @property
    def models(self) -> list[FreeModel]:
        return list(self._models)

    @property
    def default_model(self) -> FreeModel | None:
        return self._models[0] if self._models else None

    def get_model(self, model_id: str) -> FreeModel | None:
        return next((m for m in self._models if m.id == model_id), None)

    async def _periodic_refresh(self) -> None:
        while True:
            await asyncio.sleep(CACHE_TTL)
            await self.refresh()


model_cache = ModelCache()
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
uv run pytest tests/test_models.py -v
```
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_models.py
git commit -m "feat: add ModelCache with free model filtering and weekly ranking"
```

---

### Task 5: Proxy Forwarding

**Files:**
- Create: `tests/test_proxy.py`
- Create: `app/proxy.py`

- [ ] **Step 1: Write failing tests for model resolution**

Create `tests/test_proxy.py`:

```python
import pytest

from app.models import model_cache
from app.proxy import resolve_model


@pytest.fixture(autouse=True)
def setup_cache():
    from app.models import FreeModel

    model_cache._models = [
        FreeModel(id="test/model-a:free", name="A", context_length=8192, created=1000),
        FreeModel(id="test/model-b:free", name="B", context_length=32768, created=2000),
    ]
    yield
    model_cache._models = []


class TestResolveModel:
    @pytest.mark.asyncio
    async def test_auto_returns_default(self):
        mid, err = await resolve_model("auto")
        assert mid == "test/model-a:free"
        assert err is None

    @pytest.mark.asyncio
    async def test_none_returns_default(self):
        mid, err = await resolve_model(None)
        assert mid == "test/model-a:free"
        assert err is None

    @pytest.mark.asyncio
    async def test_empty_string_returns_default(self):
        mid, err = await resolve_model("")
        assert mid == "test/model-a:free"

    @pytest.mark.asyncio
    async def test_specific_model_found(self):
        mid, err = await resolve_model("test/model-b:free")
        assert mid == "test/model-b:free"
        assert err is None

    @pytest.mark.asyncio
    async def test_specific_model_not_found(self):
        mid, err = await resolve_model("nonexistent")
        assert mid is None
        assert "not found" in err

    @pytest.mark.asyncio
    async def test_free_random_picks_from_cache(self):
        mid, err = await resolve_model("free-random")
        assert mid in ["test/model-a:free", "test/model-b:free"]
        assert err is None

    @pytest.mark.asyncio
    async def test_auto_no_models_returns_error(self):
        model_cache._models = []
        mid, err = await resolve_model("auto")
        assert mid is None
        assert "No free models" in err
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
uv run pytest tests/test_proxy.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.proxy'`

- [ ] **Step 3: Write proxy module**

Create `app/proxy.py`:

```python
from __future__ import annotations

import logging
import random

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import OPENROUTER_BASE_URL
from app.models import model_cache

logger = logging.getLogger(__name__)


async def resolve_model(requested_model: str | None) -> tuple[str | None, str | None]:
    if not requested_model or requested_model == "auto":
        default = model_cache.default_model
        if not default:
            return None, "No free models available"
        return default.id, None
    if requested_model == "free-random":
        models = model_cache.models
        if not models:
            return None, "No free models available"
        return random.choice(models).id, None
    model = model_cache.get_model(requested_model)
    if not model:
        return None, f"Model '{requested_model}' not found. GET /v1/models for available models."
    return requested_model, None


async def forward_chat(request: Request) -> JSONResponse | StreamingResponse:
    auth = request.headers.get("Authorization")
    if not auth:
        return JSONResponse(
            status_code=401,
            content={"error": {"message": "OpenRouter API Key required", "type": "auth_error"}},
        )

    body = await request.json()
    model_id, error = await resolve_model(body.get("model"))
    if error:
        status = 503 if "No free models" in error else 404
        return JSONResponse(
            status_code=status,
            content={"error": {"message": error, "type": "invalid_request_error"}},
        )

    body["model"] = model_id
    is_stream = body.get("stream", False)
    headers = {"Authorization": auth, "Content-Type": "application/json"}

    client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
    try:
        if is_stream:
            return await _stream_response(client, body, headers)
        return await _non_stream_response(client, body, headers)
    except httpx.RequestError as e:
        await client.aclose()
        logger.error("OpenRouter request failed: %s", e)
        return JSONResponse(
            status_code=502,
            content={"error": {"message": "OpenRouter service temporarily unavailable", "type": "server_error"}},
        )


async def _stream_response(
    client: httpx.AsyncClient, body: dict, headers: dict[str, str]
) -> StreamingResponse:
    req = client.build_request(
        "POST", f"{OPENROUTER_BASE_URL}/chat/completions", json=body, headers=headers
    )
    resp = await client.send(req, stream=True)

    async def stream():
        try:
            async for chunk in resp.aiter_bytes():
                yield chunk
        finally:
            await resp.aclose()
            await client.aclose()

    return StreamingResponse(
        stream(),
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type"),
    )


async def _non_stream_response(
    client: httpx.AsyncClient, body: dict, headers: dict[str, str]
) -> JSONResponse:
    try:
        resp = await client.post(
            f"{OPENROUTER_BASE_URL}/chat/completions", json=body, headers=headers
        )
        return JSONResponse(status_code=resp.status_code, content=resp.json())
    finally:
        await client.aclose()
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
uv run pytest tests/test_proxy.py -v
```
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/proxy.py tests/test_proxy.py
git commit -m "feat: add proxy with model resolution and streaming support"
```

---

### Task 6: API Routes

**Files:**
- Create: `tests/test_api.py`
- Create: `app/main.py`

- [ ] **Step 1: Write failing tests for API routes**

Create `tests/test_api.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import model_cache


class TestModelsEndpoint:
    @pytest.mark.asyncio
    async def test_list_models(self, api_client):
        resp = await api_client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert len(data["data"]) == 2
        assert data["data"][0]["id"] == "test/model-a:free"
        assert data["data"][0]["context_length"] == 8192

    @pytest.mark.asyncio
    async def test_get_single_model(self, api_client):
        resp = await api_client.get("/v1/models/test/model-a:free")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "test/model-a:free"
        assert data["object"] == "model"
        assert data["owned_by"] == "openrouter-free-proxy"

    @pytest.mark.asyncio
    async def test_get_model_not_found(self, api_client):
        resp = await api_client.get("/v1/models/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_models_empty_cache(self, mock_lifespan, api_client):
        model_cache._models = []
        resp = await api_client.get("/v1/models")
        assert resp.status_code == 200
        assert resp.json()["data"] == []


class TestChatCompletions:
    @pytest.mark.asyncio
    async def test_no_auth_returns_401(self, api_client):
        resp = await api_client.post("/v1/chat/completions", json={"model": "auto"})
        assert resp.status_code == 401
        assert "API Key required" in resp.json()["error"]["message"]

    @pytest.mark.asyncio
    async def test_auto_model_resolved(self, api_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "chatcmpl-1", "choices": [{"message": {"role": "assistant", "content": "Hi"}}]}

        with patch("app.proxy.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value
            instance.post = AsyncMock(return_value=mock_resp)
            instance.aclose = AsyncMock()

            resp = await api_client.post(
                "/v1/chat/completions",
                json={"model": "auto", "messages": [{"role": "user", "content": "hi"}]},
                headers={"Authorization": "Bearer test-key"},
            )
            assert resp.status_code == 200
            call_body = instance.post.call_args[1]["json"]
            assert call_body["model"] == "test/model-a:free"

    @pytest.mark.asyncio
    async def test_forward_error_from_openrouter(self, api_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.json.return_value = {"error": {"message": "Rate limited", "type": "rate_limit"}}

        with patch("app.proxy.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value
            instance.post = AsyncMock(return_value=mock_resp)
            instance.aclose = AsyncMock()

            resp = await api_client.post(
                "/v1/chat/completions",
                json={"model": "test/model-a:free", "messages": [{"role": "user", "content": "hi"}]},
                headers={"Authorization": "Bearer test-key"},
            )
            assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_streaming_request(self, api_client):
        async def mock_aiter():
            yield b'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\n'
            yield b"data: [DONE]\n\n"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "text/event-stream"}
        mock_resp.aiter_bytes = mock_aiter
        mock_resp.aclose = AsyncMock()

        with patch("app.proxy.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value
            instance.build_request = MagicMock(return_value=MagicMock())
            instance.send = AsyncMock(return_value=mock_resp)
            instance.aclose = AsyncMock()

            resp = await api_client.post(
                "/v1/chat/completions",
                json={"model": "auto", "messages": [{"role": "user", "content": "hi"}], "stream": True},
                headers={"Authorization": "Bearer test-key"},
            )
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_model_returns_404(self, api_client):
        resp = await api_client.post(
            "/v1/chat/completions",
            json={"model": "nonexistent", "messages": [{"role": "user", "content": "hi"}]},
            headers={"Authorization": "Bearer test-key"},
        )
        assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
uv run pytest tests/test_api.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: Write FastAPI application**

Create `app/main.py`:

```python
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.models import model_cache

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await model_cache.start()
    logging.getLogger(__name__).info("Started with %d free models", len(model_cache.models))
    yield
    await model_cache.stop()


app = FastAPI(title="OpenRouterFree", version="0.1.0", lifespan=lifespan)


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    from app.proxy import forward_chat

    return await forward_chat(request)


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": m.id,
                "object": "model",
                "created": m.created,
                "owned_by": "openrouter-free-proxy",
                "context_length": m.context_length,
            }
            for m in model_cache.models
        ],
    }


@app.get("/v1/models/{model_id:path}")
async def get_model(model_id: str):
    model = model_cache.get_model(model_id)
    if not model:
        return JSONResponse(
            status_code=404,
            content={"error": {"message": f"Model '{model_id}' not found"}},
        )
    return {
        "id": model.id,
        "object": "model",
        "created": model.created,
        "owned_by": "openrouter-free-proxy",
        "context_length": model.context_length,
    }
```

- [ ] **Step 4: Run all tests**

Run:
```bash
uv run pytest -v
```
Expected: All tests PASS (7 model tests + 7 proxy tests + 9 API tests = 23 tests).

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_api.py
git commit -m "feat: add FastAPI routes for chat completions and model listing"
```

---

### Task 7: Docker

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`

- [ ] **Step 1: Write Dockerfile**

Create `Dockerfile`:

```dockerfile
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app/ app/

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Write docker-compose.yml**

Create `docker-compose.yml`:

```yaml
services:
  openrouter-free:
    build: .
    ports:
      - "${PORT:-8000}:8000"
    environment:
      - PORT=8000
      - CACHE_TTL=${CACHE_TTL:-600}
      - OPENROUTER_BASE_URL=${OPENROUTER_BASE_URL:-https://openrouter.ai/api/v1}
    restart: unless-stopped
```

- [ ] **Step 3: Write .dockerignore**

Create `.dockerignore`:

```
.git
__pycache__
*.pyc
.pytest_cache
tests/
docs/
.env
.venv
```

- [ ] **Step 4: Verify Docker build**

Run:
```bash
docker build -t openrouter-free .
```
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile docker-compose.yml .dockerignore
git commit -m "feat: add Docker and docker-compose configuration"
```

---

### Task 8: Documentation and Final Verification

**Files:**
- Create: `.env.example`
- Create: `README.md`

- [ ] **Step 1: Write .env.example**

Create `.env.example`:

```
PORT=8000
CACHE_TTL=600
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

- [ ] **Step 2: Write README.md**

Create `README.md`:

```markdown
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
```

- [ ] **Step 3: Run full test suite**

Run:
```bash
uv run pytest -v
```
Expected: All 23 tests PASS.

- [ ] **Step 4: Smoke test with real API**

Run:
```bash
uv run uvicorn app.main:app &
sleep 5
curl -s http://localhost:8000/v1/models | python -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d[\"data\"])} free models available')"
# Stop the server
kill %1
```
Expected: Prints the number of free models (e.g. `28 free models available`).

- [ ] **Step 5: Final commit**

```bash
git add .env.example README.md
git commit -m "docs: add README with usage instructions and environment config"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- [x] Auto-detect free models → Task 4 (`_parse_free_models` filters by pricing)
- [x] Sort by weekly tokens → Task 4 (API called with `?order=top-weekly`, order preserved)
- [x] Default to highest weekly tokens → Task 5 (`resolve_model("auto")` returns first model)
- [x] OpenAI-compatible API → Task 6 (POST /v1/chat/completions, GET /v1/models)
- [x] Query free model list → Task 6 (GET /v1/models)
- [x] Manually specify model → Task 5 (resolve_model with specific ID)
- [x] Streaming support → Task 5 (`_stream_response`)
- [x] Cache refresh every 10 min → Task 4 (`_periodic_refresh`)
- [x] User brings own API Key → Task 5 (Authorization header passthrough)
- [x] Docker deployment → Task 7
- [x] uv package manager → Task 1

**2. Placeholder scan:** No TBD, TODO, or vague instructions found.

**3. Type consistency:** `FreeModel` fields (`id`, `name`, `context_length`, `created`) used consistently across all files. `resolve_model` returns `tuple[str | None, str | None]` matching usage in `forward_chat`.
