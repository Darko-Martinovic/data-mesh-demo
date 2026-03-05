"""Register inventory data products with the central catalogue on startup."""

import asyncio
import os

import httpx

CATALOGUE_URL = os.environ.get("CATALOGUE_URL", "http://localhost:8000")
SELF_URL = os.environ.get("SELF_URL", "http://localhost:8003")

MAX_RETRIES = 10
RETRY_DELAY = 2

_PRODUCTS = [
    {
        "name": "stock-levels",
        "domain": "inventory",
        "description": "Current stock levels and availability per SKU.",
        "version": "1.0.0",
        "endpoint": f"{SELF_URL}/data-products/stock-levels",
        "tags": ["inventory", "stock", "availability", "supply-chain"],
        "owner": "inventory-team",
        "sla": {"uptime": "99.9%", "freshness": "real-time"},
        "schema_definition": {
            "sku": "string",
            "name": "string",
            "stock_qty": "integer",
            "threshold": "integer",
        },
    },
    {
        "name": "low-stock-alerts",
        "domain": "inventory",
        "description": "Products currently below their reorder threshold.",
        "version": "1.0.0",
        "endpoint": f"{SELF_URL}/data-products/low-stock-alerts",
        "tags": ["inventory", "alerts", "low-stock", "operations", "supply-chain"],
        "owner": "inventory-team",
        "sla": {"uptime": "99.9%", "freshness": "real-time"},
        "schema_definition": {
            "sku": "string",
            "name": "string",
            "stock_qty": "integer",
            "threshold": "integer",
            "deficit": "integer",
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
