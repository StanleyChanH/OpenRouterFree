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
