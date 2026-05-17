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
