"""Abstract base class for AI providers."""

from abc import ABC, abstractmethod
from typing import Any


class BaseAIProvider(ABC):
    """Interface that all AI providers must implement."""

    provider_name: str

    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
        ...

    @abstractmethod
    async def test_connection(self) -> dict[str, Any]:
        """Test the provider connection. Returns {"ok": bool, "message": str, "model": str}."""
        ...
