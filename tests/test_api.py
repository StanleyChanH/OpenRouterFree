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
