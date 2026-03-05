"""LLM Router: primary/fallback provider routing with circuit breaker and metrics."""

import time
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.logging import log
from app.integrations.base_provider import BaseAIProvider
from app.integrations.claude_ai import ClaudeProvider
from app.integrations.openrouter_provider import OpenRouterProvider
from app.integrations.mock_provider import MockProvider
from app.models.models import AICall
from app.services.settings_service import get_setting

# Circuit breaker state (in-memory, acceptable for single-process)
_circuit_state: dict[str, Any] = {
    "primary_failures": 0,
    "primary_disabled_until": 0.0,
    "fallback_failures": 0,
    "fallback_disabled_until": 0.0,
}
CIRCUIT_THRESHOLD = 5
CIRCUIT_COOLDOWN = 60

# Status codes that should NOT trigger fallback (fail immediately)
NO_FALLBACK_STATUS_CODES = {400, 401, 403}


class LLMRouter:
    """Routes AI calls through primary -> fallback providers with circuit breaker."""

    async def _build_provider(self, db: AsyncSession, role: str) -> Optional[BaseAIProvider]:
        """Build a provider instance from DB settings. role is 'primary' or 'fallback'."""
        provider_type = await get_setting(db, f"ai_{role}_provider")
        if not provider_type or provider_type == "mock":
            return MockProvider()

        if provider_type == "anthropic":
            api_key = await get_setting(db, "anthropic_api_key")
            model = await get_setting(db, "anthropic_model")
            if not api_key or not model:
                return None
            return ClaudeProvider(api_key=api_key, model=model)

        if provider_type == "openrouter":
            api_key = await get_setting(db, "openrouter_api_key")
            model = await get_setting(db, "openrouter_model")
            base_url = await get_setting(db, "openrouter_base_url")
            if not api_key or not model:
                return None
            return OpenRouterProvider(api_key=api_key, model=model, base_url=base_url)

        return None

    def _is_circuit_open(self, role: str) -> bool:
        return time.time() < _circuit_state.get(f"{role}_disabled_until", 0)

    def _record_failure(self, role: str):
        key = f"{role}_failures"
        _circuit_state[key] = _circuit_state.get(key, 0) + 1
        if _circuit_state[key] >= CIRCUIT_THRESHOLD:
            _circuit_state[f"{role}_disabled_until"] = time.time() + CIRCUIT_COOLDOWN
            log.warning("circuit_breaker_tripped", role=role)

    def _record_success(self, role: str):
        _circuit_state[f"{role}_failures"] = 0

    async def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
        """Try primary provider, fall back if eligible error."""
        async with async_session_factory() as db:
            return await self._try_with_fallback(db, system_prompt, user_prompt, max_tokens)

    async def _try_with_fallback(
        self, db: AsyncSession, system_prompt: str, user_prompt: str, max_tokens: int
    ) -> str:
        primary = await self._build_provider(db, "primary")
        fallback = await self._build_provider(db, "fallback")

        # Try primary (with 1 retry before fallback)
        if primary and not self._is_circuit_open("primary"):
            for attempt in range(2):
                start = time.time()
                try:
                    result = await primary.generate(system_prompt, user_prompt, max_tokens)
                    latency = int((time.time() - start) * 1000)
                    await self._log_call(
                        db, primary.provider_name, getattr(primary, "model", "mock"),
                        latency, "success", None, False, None,
                    )
                    self._record_success("primary")
                    return result
                except Exception as e:
                    latency = int((time.time() - start) * 1000)
                    status_code = self._extract_status_code(e)
                    if status_code in NO_FALLBACK_STATUS_CODES:
                        await self._log_call(
                            db, primary.provider_name, getattr(primary, "model", "mock"),
                            latency, "error", str(status_code), False, None,
                        )
                        raise
                    self._record_failure("primary")
                    if attempt == 1:
                        break

        # Try fallback
        if fallback and not self._is_circuit_open("fallback"):
            start = time.time()
            try:
                result = await fallback.generate(system_prompt, user_prompt, max_tokens)
                latency = int((time.time() - start) * 1000)
                await self._log_call(
                    db, fallback.provider_name, getattr(fallback, "model", "mock"),
                    latency, "success", None, True, "primary_failed",
                )
                self._record_success("fallback")
                return result
            except Exception:
                self._record_failure("fallback")

        # Both failed
        await self._log_call(db, "none", "none", 0, "error", "all_providers_failed", True, "total_failure")
        return "[AI GENERATION FAILED -- please check provider configuration in Admin Settings]"

    def _extract_status_code(self, exc: Exception) -> Optional[int]:
        if hasattr(exc, "response") and hasattr(exc.response, "status_code"):
            return exc.response.status_code
        return None

    async def _log_call(
        self, db, provider, model, latency_ms, status, error_type, fallback_used, fallback_reason
    ):
        try:
            db.add(AICall(
                provider=provider, model=model, latency_ms=latency_ms,
                status=status, error_type=error_type,
                fallback_used=fallback_used, fallback_reason=fallback_reason,
            ))
            await db.commit()
        except Exception:
            log.error("failed_to_log_ai_call")


_router = None


def get_llm_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
