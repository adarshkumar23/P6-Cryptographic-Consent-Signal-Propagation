"""
Read-only client for core's export endpoint. Per PHASE 6 of the build
spec, this satellite EXTENDS core's existing consent_records, it does
not duplicate a parallel consent management system.

The exact shape of these export endpoints is ASSUMED — see
ASSUMPTIONS.md — because no real core repository/clone was available
in this environment to verify the actual contract against. Before
relying on this in production, verify against real core source.
"""
import httpx

from app.config import get_settings


class CoreReadClient:
    def __init__(self, http_client: httpx.Client | None = None):
        settings = get_settings()
        self.http_client = http_client or httpx.Client(
            base_url=settings.core_base_url,
            headers={"Authorization": f"Bearer {settings.core_api_key}"}
            if settings.core_api_key
            else {},
            timeout=10.0,
        )

    def fetch_consent_records(self, processing_activity_id: str | None = None) -> list[dict]:
        params = {"processing_activity_id": processing_activity_id} if processing_activity_id else {}
        response = self.http_client.get("/export/consent_records", params=params)
        response.raise_for_status()
        return response.json()

    def fetch_registered_processors(self, processing_activity_id: str | None = None) -> list[dict]:
        params = {"processing_activity_id": processing_activity_id} if processing_activity_id else {}
        response = self.http_client.get("/export/registered_processors", params=params)
        response.raise_for_status()
        return response.json()
