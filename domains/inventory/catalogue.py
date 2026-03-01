"""Register inventory data products with the central catalogue on startup."""

import os

import httpx

CATALOGUE_URL = os.environ.get("CATALOGUE_URL", "http://localhost:8000")
SELF_URL = os.environ.get("SELF_URL", "http://localhost:8003")

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
    async with httpx.AsyncClient(timeout=10.0) as client:
        for product in _PRODUCTS:
            try:
                r = await client.post(f"{CATALOGUE_URL}/catalogue/register", json=product)
                print(f"[CATALOGUE] Registered '{product['name']}': HTTP {r.status_code}", flush=True)
            except Exception as exc:
                print(f"[CATALOGUE] Could not register '{product['name']}': {exc}", flush=True)
