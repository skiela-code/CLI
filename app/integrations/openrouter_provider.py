"""OpenRouter AI provider using OpenAI-compatible chat completions API."""

import asyncio
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.logging import log
from app.integrations.base_provider import BaseAIProvider

_semaphore = None


def _get_semaphore():
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(3)
    return _semaphore


class OpenRouterProvider(BaseAIProvider):
    provider_name = "openrouter"
    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url or self.DEFAULT_BASE_URL

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
    async def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
        sem = _get_semaphore()
        async with sem:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    self.base_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://clm-lite.local",
                        "X-Title": "CLM-lite Proposal Generator",
                    },
                    json={
                        "model": self.model,
                        "max_tokens": max_tokens,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]

    async def test_connection(self) -> dict[str, Any]:
        try:
            result = await self.generate("You are a test assistant.", "Say hello.", max_tokens=10)
            return {"ok": True, "message": f"Connected: {result[:50]}", "model": self.model}
        except Exception as e:
            log.error("openrouter_test_failed", error=str(e))
            return {"ok": False, "message": str(e), "model": self.model}
