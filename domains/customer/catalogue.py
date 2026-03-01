"""Register customer data products with the central catalogue on startup."""

import os

import httpx

CATALOGUE_URL = os.environ.get("CATALOGUE_URL", "http://localhost:8000")
SELF_URL = os.environ.get("SELF_URL", "http://localhost:8001")

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
    async with httpx.AsyncClient(timeout=10.0) as client:
        for product in _PRODUCTS:
            try:
                r = await client.post(f"{CATALOGUE_URL}/catalogue/register", json=product)
                print(f"[CATALOGUE] Registered '{product['name']}': HTTP {r.status_code}", flush=True)
            except Exception as exc:
                print(f"[CATALOGUE] Could not register '{product['name']}': {exc}", flush=True)
