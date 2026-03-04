"""Claude AI provider adapter with mock mode and retries."""

import asyncio
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import log

settings = get_settings()

_ai_semaphore = None


def _get_ai_semaphore():
    global _ai_semaphore
    if _ai_semaphore is None:
        _ai_semaphore = asyncio.Semaphore(3)
    return _ai_semaphore


class ClaudeProvider:
    """Provider adapter for Anthropic Claude API.

    Uses httpx directly (no vendor SDK) for full async control.
    """

    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self):
        self.api_key = settings.anthropic_api_key
        self.model = settings.anthropic_model
        self.mock = settings.anthropic_mock_mode

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
    async def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
        """Send a prompt to Claude and return the text response."""
        if self.mock:
            return self._mock_response(user_prompt)

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

    def _mock_response(self, prompt: str) -> str:
        """Return realistic mock content for testing without API key."""
        if "narrative" in prompt.lower() or "pricing" in prompt.lower():
            return (
                "## Executive Summary\n\n"
                "We are pleased to present this commercial offer tailored to your organization's needs. "
                "Our solution delivers enterprise-grade capabilities with a clear return on investment.\n\n"
                "## Proposed Solution\n\n"
                "Based on our analysis of your requirements, we recommend a comprehensive package "
                "that includes platform licensing, implementation services, and ongoing support.\n\n"
                "## Investment Overview\n\n"
                "The pricing outlined in the accompanying table reflects our commitment to providing "
                "competitive value. All line items have been structured to align with your stated budget "
                "parameters and procurement timeline.\n\n"
                "## Next Steps\n\n"
                "1. Review and confirm the scope of services\n"
                "2. Schedule a technical deep-dive session\n"
                "3. Finalize contract terms\n"
                "4. Target go-live within 8 weeks of signing\n\n"
                "We look forward to partnering with you on this initiative."
            )
        return (
            "This section has been generated by the AI assistant based on the provided context. "
            "It contains professionally written content suitable for business documents. "
            "In production mode, this would be generated by Claude with full context awareness."
        )
