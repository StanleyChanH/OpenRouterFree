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
