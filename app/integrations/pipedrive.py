"""Async Pipedrive client with mock mode and retries."""

import uuid
from datetime import datetime
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import log

settings = get_settings()

# Concurrency limiter
_semaphore = None


def _get_semaphore():
    import asyncio
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(5)
    return _semaphore


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------
MOCK_DEALS = [
    {
        "id": 1001,
        "title": "Acme Corp — Enterprise License",
        "org_name": "Acme Corporation",
        "person_name": "John Smith",
        "person_email": "john.smith@acme.com",
        "value": 125000,
        "currency": "EUR",
        "status": "open",
        "custom_fields": {"industry": "Technology", "region": "EMEA"},
    },
    {
        "id": 1002,
        "title": "Beta Industries — Consulting Package",
        "org_name": "Beta Industries Ltd",
        "person_name": "Marie Dupont",
        "person_email": "m.dupont@beta-ind.com",
        "value": 45000,
        "currency": "EUR",
        "status": "open",
        "custom_fields": {"industry": "Manufacturing", "region": "EU"},
    },
    {
        "id": 1003,
        "title": "Gamma Health — SaaS Subscription",
        "org_name": "Gamma Health GmbH",
        "person_name": "Hans Müller",
        "person_email": "hans@gammahealth.de",
        "value": 78000,
        "currency": "EUR",
        "status": "open",
        "custom_fields": {"industry": "Healthcare", "region": "DACH"},
    },
]


class PipedriveClient:
    """Async Pipedrive API client."""

    def __init__(self):
        self.base_url = settings.pipedrive_base_url
        self.token = settings.pipedrive_api_token
        self.mock = settings.pipedrive_mock_mode

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        sem = _get_semaphore()
        async with sem:
            async with httpx.AsyncClient(timeout=30) as client:
                url = f"{self.base_url}{path}"
                params = kwargs.pop("params", {})
                params["api_token"] = self.token
                resp = await client.request(method, url, params=params, **kwargs)
                resp.raise_for_status()
                return resp.json()

    async def list_deals(self, search: str | None = None) -> list[dict]:
        if self.mock:
            if search:
                return [d for d in MOCK_DEALS if search.lower() in d["title"].lower()]
            return MOCK_DEALS

        if search:
            data = await self._request("GET", "/deals/search", params={"term": search})
            items = data.get("data", {}).get("items", [])
            return [self._map_deal(i.get("item", {})) for i in items]

        data = await self._request("GET", "/deals", params={"limit": 50})
        return [self._map_deal(d) for d in (data.get("data") or [])]

    async def get_deal(self, deal_id: int) -> dict:
        if self.mock:
            for d in MOCK_DEALS:
                if d["id"] == deal_id:
                    return d
            raise ValueError(f"Mock deal {deal_id} not found")
        data = await self._request("GET", f"/deals/{deal_id}")
        return self._map_deal(data.get("data", {}))

    async def attach_file(self, deal_id: int, file_path: str, filename: str) -> dict:
        if self.mock:
            log.info("mock_attach_file", deal_id=deal_id, filename=filename)
            return {"success": True, "mock": True}

        with open(file_path, "rb") as f:
            return await self._request(
                "POST", "/files",
                data={"deal_id": deal_id},
                files={"file": (filename, f, "application/octet-stream")},
            )

    async def create_note(self, deal_id: int, content: str) -> dict:
        if self.mock:
            log.info("mock_create_note", deal_id=deal_id)
            return {"success": True, "mock": True}

        return await self._request(
            "POST", "/notes",
            json={"deal_id": deal_id, "content": content},
        )

    @staticmethod
    def _map_deal(raw: dict) -> dict:
        org = raw.get("org_id", {}) or {}
        person = raw.get("person_id", {}) or {}
        return {
            "id": raw.get("id"),
            "title": raw.get("title", ""),
            "org_name": org.get("name", "") if isinstance(org, dict) else str(org),
            "person_name": person.get("name", "") if isinstance(person, dict) else str(person),
            "person_email": (person.get("email", [{}]) or [{}])[0].get("value", "") if isinstance(person, dict) else "",
            "value": raw.get("value", 0),
            "currency": raw.get("currency", "EUR"),
            "status": raw.get("status", "open"),
            "custom_fields": {},
        }
