"""
Pushes ALREADY-SIGNED, ALREADY-VERIFIED records to core. Core never
receives a private key and never performs signature verification on
this satellite's behalf — see scripts/boundary_audit.sh. Core
independently re-verifies before acting (see core-side-patch/routes/
patent_ingest_p6.py), per the standing rule: "satellite computes and
signs; it never decides what core does with a verified result."

The wire contract used here (POST /internal/vendor-risk/findings,
POST /internal/consent-propagation/records) is an ASSUMPTION — see
ASSUMPTIONS.md — because no real core repository was available to
verify against.
"""
import httpx

from app.config import get_settings


class CorePushClient:
    def __init__(self, http_client: httpx.Client | None = None):
        settings = get_settings()
        self.base_url = settings.core_base_url
        self.api_key = settings.core_api_key
        self.http_client = http_client or httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
            timeout=10.0,
        )

    def push_propagation_record(self, record_payload: dict) -> dict:
        response = self.http_client.post(
            "/internal/consent-propagation/records", json=record_payload
        )
        response.raise_for_status()
        return response.json()

    def push_vendor_risk_finding(self, finding_payload: dict) -> dict:
        """finding_payload shape assumed: vendor_id, finding_type,
        severity, description, source_system. See ASSUMPTIONS.md."""
        response = self.http_client.post(
            "/internal/vendor-risk/findings", json=finding_payload
        )
        response.raise_for_status()
        return response.json()
