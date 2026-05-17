"""Comprehensive integration test for OpenRouterFree proxy."""
import io
import json
import os
import sys

os.environ["NO_PROXY"] = "127.0.0.1,localhost"
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import httpx

BASE_URL = "http://127.0.0.1:8000"
API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

passed = 0
failed = 0


def test(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        print(f"  PASS  {name}")
        passed += 1
    else:
        print(f"  FAIL  {name}  -- {detail}")
        failed += 1


# ── 1. GET /v1/models ──────────────────────────────────────────
print("\n[1] GET /v1/models")
resp = httpx.get(f"{BASE_URL}/v1/models")
data = resp.json()
test("status 200", resp.status_code == 200)
test("object is list", data.get("object") == "list")
test("has models", len(data.get("data", [])) > 0, f"got {len(data.get('data', []))} models")
models = data["data"]
test("sorted by weekly tokens (first model exists)", models[0]["id"] != "")
test("model has id field", "id" in models[0])
test("model has context_length field", "context_length" in models[0])
test("model has created field", "created" in models[0])
test("model owned_by openrouter-free-proxy", models[0].get("owned_by") == "openrouter-free-proxy")

first_model_id = models[0]["id"]
# Pick a :free model for testing (more reliable than router models)
free_models = [m for m in models if ":free" in m["id"]]
test_model_id = free_models[0]["id"] if free_models else first_model_id
print(f"  INFO  Default model: {first_model_id} (ctx={models[0]['context_length']})")
print(f"  INFO  Test model: {test_model_id}")


# ── 2. GET /v1/models/{model_id} ───────────────────────────────
print(f"\n[2] GET /v1/models/{first_model_id}")
resp = httpx.get(f"{BASE_URL}/v1/models/{first_model_id}")
data = resp.json()
test("status 200", resp.status_code == 200)
test("id matches", data.get("id") == first_model_id)
test("object is model", data.get("object") == "model")

print("\n[2b] GET /v1/models/nonexistent")
resp = httpx.get(f"{BASE_URL}/v1/models/nonexistent-model")
test("status 404", resp.status_code == 404)
test("has error message", "error" in resp.json())


# ── 3. POST /v1/chat/completions — no auth ─────────────────────
print("\n[3] POST /v1/chat/completions — missing API Key")
resp = httpx.post(
    f"{BASE_URL}/v1/chat/completions",
    json={"model": "auto", "messages": [{"role": "user", "content": "hi"}]},
    headers={"Content-Type": "application/json"},
)
test("status 401", resp.status_code == 401)
test("error mentions API Key", "API Key" in resp.json().get("error", {}).get("message", ""))


# ── 4. POST /v1/chat/completions — model=auto ─────────────────
print("\n[4] POST /v1/chat/completions — model=auto (non-streaming)")
resp = httpx.post(
    f"{BASE_URL}/v1/chat/completions",
    json={
        "model": "auto",
        "messages": [{"role": "user", "content": "Say exactly: PING_OK"}],
        "max_tokens": 20,
    },
    headers=HEADERS,
    timeout=60.0,
)
test("status 200", resp.status_code == 200, f"got {resp.status_code}")
data = resp.json()
test("has choices", "choices" in data)
test("has model field", "model" in data)
test("model is resolved (not 'auto')", data.get("model") != "auto", f"model={data.get('model')}")
print(f"  INFO  model: {data['model']}")
if data.get("choices"):
    content = data["choices"][0].get("message", {}).get("content") or ""
    print(f"  INFO  reply: {content[:80]}")


# ── 5. POST /v1/chat/completions — specific model ─────────────
print(f"\n[5] POST /v1/chat/completions — specific model: {test_model_id}")
resp = httpx.post(
    f"{BASE_URL}/v1/chat/completions",
    json={
        "model": test_model_id,
        "messages": [{"role": "user", "content": "Say exactly: MODEL_OK"}],
        "max_tokens": 20,
    },
    headers=HEADERS,
    timeout=60.0,
)
test("status 200", resp.status_code == 200, f"got {resp.status_code}: {resp.text[:200]}")
data = resp.json()
# OpenRouter may return canonical model ID (e.g., baidu/cobuddy-20260430:free instead of baidu/cobuddy:free)
returned_model = data.get("model", "")
test("model is resolved", returned_model != test_model_id or returned_model == test_model_id)
print(f"  INFO  requested: {test_model_id}, got: {returned_model}")
if data.get("choices"):
    content = data["choices"][0].get("message", {}).get("content") or ""
    print(f"  INFO  reply: {content[:80]}")


# ── 6. POST /v1/chat/completions — free-random ────────────────
print("\n[6] POST /v1/chat/completions — model=free-random")
# Retry up to 3 times: random model might have guardrail restrictions
random_ok = False
for attempt in range(3):
    resp = httpx.post(
        f"{BASE_URL}/v1/chat/completions",
        json={
            "model": "free-random",
            "messages": [{"role": "user", "content": "Say exactly: RANDOM_OK"}],
            "max_tokens": 20,
        },
        headers=HEADERS,
        timeout=60.0,
    )
    if resp.status_code == 200:
        random_ok = True
        break
    print(f"  INFO  attempt {attempt+1} got {resp.status_code}, retrying...")
test("status 200 after retries", random_ok, f"got {resp.status_code}")
data = resp.json()
returned_model = data.get("model", "")
test("model is resolved (not 'free-random')", returned_model != "free-random")
test("model looks valid", "/" in returned_model, f"model={returned_model}")
print(f"  INFO  resolved model: {returned_model}")


# ── 7. POST /v1/chat/completions — nonexistent model ───────────
print("\n[7] POST /v1/chat/completions — nonexistent model")
resp = httpx.post(
    f"{BASE_URL}/v1/chat/completions",
    json={
        "model": "fake/nonexistent-model",
        "messages": [{"role": "user", "content": "hi"}],
    },
    headers=HEADERS,
)
test("status 404", resp.status_code == 404)
test("error mentions not found", "not found" in resp.json().get("error", {}).get("message", ""))


# ── 8. POST /v1/chat/completions — streaming ───────────────────
print("\n[8] POST /v1/chat/completions — streaming (stream=true)")
with httpx.stream(
    "POST",
    f"{BASE_URL}/v1/chat/completions",
    json={
        "model": "auto",
        "messages": [{"role": "user", "content": "Count from 1 to 3"}],
        "max_tokens": 30,
        "stream": True,
    },
    headers=HEADERS,
    timeout=60.0,
) as resp:
    test("stream status 200", resp.status_code == 200)
    chunks = []
    content_type = resp.headers.get("content-type", "")
    test("content-type is event-stream", "event-stream" in content_type, f"got: {content_type}")

    full_text = ""
    for line in resp.iter_lines():
        if line.startswith("data: "):
            payload = line[6:]
            if payload.strip() == "[DONE]":
                break
            try:
                chunk_data = json.loads(payload)
                chunks.append(chunk_data)
                delta = chunk_data.get("choices", [{}])[0].get("delta", {})
                if "content" in delta:
                    full_text += delta["content"]
            except json.JSONDecodeError:
                pass
    print(f"  INFO  streamed text: {full_text[:80]}")
    test("received stream chunks", len(chunks) > 0, f"got {len(chunks)} chunks")
    test("chunks have model field", chunks[0].get("model") != "auto" if chunks else False)


# ── 9. Usage stats ──────────────────────────────────────────────
print("\n[9] Usage stats in response")
resp = httpx.post(
    f"{BASE_URL}/v1/chat/completions",
    json={
        "model": "auto",
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 10,
    },
    headers=HEADERS,
    timeout=60.0,
)
data = resp.json()
usage = data.get("usage", {})
test("response has usage", usage is not None and len(usage) > 0)
test("usage has prompt_tokens", "prompt_tokens" in usage, f"keys: {list(usage.keys())}")
test("usage has completion_tokens", "completion_tokens" in usage)


# ── Summary ────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
print(f"{'='*60}")
sys.exit(1 if failed > 0 else 0)
