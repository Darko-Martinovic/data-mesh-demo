"""Register customer data products with the central catalogue on startup."""

import asyncio
import os

import httpx

CATALOGUE_URL = os.environ.get("CATALOGUE_URL", "http://localhost:8000")
SELF_URL = os.environ.get("SELF_URL", "http://localhost:8001")

MAX_RETRIES = 10
RETRY_DELAY = 2

_PRODUCTS = [
    {
        "name": "customer-profiles",
        "domain": "customer",
        "description": "Full customer profile data including PII (email masked by default).",
        "version": "1.0.0",
        "endpoint": f"{SELF_URL}/data-products/customer-profiles",
        "tags": ["customer", "pii", "profiles", "identity"],
        "owner": "customer-team",
        "sla": {"uptime": "99.9%", "freshness": "real-time"},
        "schema_definition": {
            "id": "string",
            "name": "string",
            "email": "string (masked unless ?unmasked=true)",
            "segment": "enum[premium,standard,basic]",
            "status": "string",
            "created_at": "ISO8601",
        },
    },
    {
        "name": "customer-segments",
        "domain": "customer",
        "description": "Aggregated customer segmentation statistics for analytics consumers.",
        "version": "1.0.0",
        "endpoint": f"{SELF_URL}/data-products/customer-segments",
        "tags": ["customer", "segments", "analytics", "aggregated"],
        "owner": "customer-team",
        "sla": {"uptime": "99.9%", "freshness": "5 minutes"},
        "schema_definition": {
            "segment": "string",
            "count": "integer",
            "percentage": "float",
        },
    },
]


async def register_products() -> None:
    """Register data products with retry logic for catalogue availability."""
    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                for product in _PRODUCTS:
                    r = await client.post(f"{CATALOGUE_URL}/catalogue/register", json=product)
                    print(f"[CATALOGUE] Registered '{product['name']}': HTTP {r.status_code}", flush=True)
                return
        except Exception as exc:
            if attempt < MAX_RETRIES - 1:
                print(f"[CATALOGUE] Waiting for catalogue (attempt {attempt + 1}/{MAX_RETRIES})...", flush=True)
                await asyncio.sleep(RETRY_DELAY)
            else:
                print(f"[CATALOGUE] Failed to register after {MAX_RETRIES} attempts: {exc}", flush=True)
