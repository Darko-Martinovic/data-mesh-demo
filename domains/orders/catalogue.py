"""Register orders data products with the central catalogue on startup."""

import os

import httpx

CATALOGUE_URL = os.environ.get("CATALOGUE_URL", "http://localhost:8000")
SELF_URL = os.environ.get("SELF_URL", "http://localhost:8002")

_PRODUCTS = [
    {
        "name": "order-history",
        "domain": "orders",
        "description": "Complete order transaction history with status and totals.",
        "version": "1.0.0",
        "endpoint": f"{SELF_URL}/data-products/order-history",
        "tags": ["orders", "transactions", "history", "commerce"],
        "owner": "orders-team",
        "sla": {"uptime": "99.9%", "freshness": "real-time"},
        "schema_definition": {
            "id": "string",
            "customer_id": "string",
            "sku": "string",
            "quantity": "integer",
            "total": "float",
            "status": "enum[confirmed,cancelled]",
            "created_at": "ISO8601",
        },
    },
    {
        "name": "revenue-summary",
        "domain": "orders",
        "description": "Aggregated revenue metrics broken down by SKU.",
        "version": "1.0.0",
        "endpoint": f"{SELF_URL}/data-products/revenue-summary",
        "tags": ["orders", "revenue", "analytics", "aggregated", "finance"],
        "owner": "orders-team",
        "sla": {"uptime": "99.9%", "freshness": "real-time"},
        "schema_definition": {
            "total_revenue": "float",
            "total_orders": "integer",
            "average_order_value": "float",
            "by_sku": "object{revenue: float, orders: int}",
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
