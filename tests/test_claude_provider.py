"""Tests for the Claude AI provider adapter (mock mode)."""

import pytest
import asyncio

from app.integrations.claude_ai import ClaudeProvider


@pytest.fixture
def provider():
    p = ClaudeProvider()
    p.mock = True
    return p


@pytest.mark.asyncio
async def test_mock_generate(provider):
    result = await provider.generate("system", "user prompt")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_mock_narrative(provider):
    result = await provider.generate_narrative(
        deal_context={"title": "Test Deal", "org_name": "Test Corp"},
        pricing_data=[{"description": "Item", "quantity": 1, "unit_price": 1000}],
        length="short",
    )
    assert "Summary" in result or "solution" in result.lower() or "offer" in result.lower()


@pytest.mark.asyncio
async def test_mock_section(provider):
    result = await provider.generate_section(
        "Write an executive summary",
        {"title": "Test", "org_name": "Acme"},
    )
    assert isinstance(result, str)
    assert len(result) > 10
