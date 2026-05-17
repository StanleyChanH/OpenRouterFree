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
