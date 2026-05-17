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
