import os

PORT = int(os.environ.get("PORT", "8000"))
CACHE_TTL = int(os.environ.get("CACHE_TTL", "600"))
OPENROUTER_BASE_URL = os.environ.get(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
)
