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
