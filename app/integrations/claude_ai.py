"""Claude AI provider adapter for Anthropic API."""

import asyncio
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.logging import log
from app.integrations.base_provider import BaseAIProvider

_ai_semaphore = None


def _get_ai_semaphore():
    global _ai_semaphore
    if _ai_semaphore is None:
        _ai_semaphore = asyncio.Semaphore(3)
    return _ai_semaphore


class ClaudeProvider(BaseAIProvider):
    """Provider adapter for Anthropic Claude API.

    Uses httpx directly (no vendor SDK) for full async control.
    """

    API_URL = "https://api.anthropic.com/v1/messages"
    provider_name = "anthropic"

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
    async def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
        """Send a prompt to Claude and return the text response."""
        sem = _get_ai_semaphore()
        async with sem:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    self.API_URL,
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "max_tokens": max_tokens,
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": user_prompt}],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data["content"][0]["text"]

    async def test_connection(self) -> dict[str, Any]:
        try:
            result = await self.generate("You are a test assistant.", "Say hello.", max_tokens=10)
            return {"ok": True, "message": f"Connected: {result[:50]}", "model": self.model}
        except Exception as e:
            log.error("claude_test_failed", error=str(e))
            return {"ok": False, "message": str(e), "model": self.model}

    async def generate_narrative(
        self,
        deal_context: dict[str, Any],
        pricing_data: list[dict],
        length: str = "medium",
        doc_type: str = "commercial_offer",
    ) -> str:
        """Generate a narrative section for a commercial document."""
        system = (
            "You are a professional proposal writer. Generate clear, persuasive "
            "business document sections. Use the pricing data as the single source of truth. "
            "Do NOT invent prices or quantities — reference them from the provided table."
        )
        user = (
            f"Document type: {doc_type}\n"
            f"Length: {length}\n"
            f"Deal: {deal_context.get('title', 'N/A')}\n"
            f"Client: {deal_context.get('org_name', 'N/A')}\n"
            f"Contact: {deal_context.get('contact_name', 'N/A')}\n\n"
            f"Pricing table:\n"
        )
        for item in pricing_data:
            user += (
                f"  - {item['description']}: {item['quantity']}x @ {item['unit_price']} "
                f"(discount {item.get('discount_pct', 0)}%)\n"
            )
        user += (
            "\nWrite a professional narrative section that:\n"
            "1. Introduces the solution\n"
            "2. References the pricing accurately\n"
            "3. Highlights value propositions\n"
            "4. Includes next steps\n"
        )
        return await self.generate(system, user)

    async def generate_section(self, prompt: str, context: dict[str, Any]) -> str:
        """Generate a single AI-driven section for template placeholder."""
        system = "You are a document section writer. Generate professional content."
        user = f"{prompt}\n\nContext:\n"
        for k, v in context.items():
            user += f"  {k}: {v}\n"
        return await self.generate(system, user)
