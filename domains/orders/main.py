"""Orders Domain — owns order transactions and revenue data products."""

import os
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator, List

import httpx
from fastapi import FastAPI, HTTPException

from event_bus.bus import EventBus
import catalogue
import db
from models import CreateOrderRequest, Order, RevenueSummary

CUSTOMER_URL = os.environ.get("CUSTOMER_URL", "http://localhost:8001")
INVENTORY_URL = os.environ.get("INVENTORY_URL", "http://localhost:8003")

# Simplified price catalogue — a real system would query a pricing service
_SKU_PRICE: dict = {
    "SKU-A": 29.99,
    "SKU-B": 49.99,
    "SKU-C": 19.99,
    "SKU-D": 99.99,
    "SKU-E": 14.99,
}


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db.init_db()
    # Registration commented out to demonstrate manual registration via API
    # await catalogue.register_products()
    yield


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Orders Domain",
    description="Owns order transactions and revenue data products.",
    version="1.0.0",
    lifespan=lifespan,
)

bus = EventBus.get_instance()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get(
    "/data-products/order-history",
    response_model=List[Order],
    summary="List all orders",
)
def list_orders():
    return db.get_all()


@app.get(
    "/data-products/order-history/{order_id}",
    response_model=Order,
    summary="Get a single order by ID",
)
def get_order(order_id: str):
    order = db.get_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.post(
    "/data-products/order-history",
    response_model=Order,
    status_code=201,
    summary="Create an order — validates customer, reserves stock, publishes event",
)
async def create_order(req: CreateOrderRequest):
    async with httpx.AsyncClient(timeout=10.0) as client:
        # ── Step a: Validate customer exists ────────────────────────────────
        customer_resp = await client.get(
            f"{CUSTOMER_URL}/data-products/customer-profiles/{req.customer_id}"
        )
        if customer_resp.status_code == 404:
            raise HTTPException(status_code=400, detail="Customer not found")
        if customer_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Customer service error")

        print(
            f"[ORDERS] Customer {req.customer_id} validated "
            f"({customer_resp.json()['name']})",
            flush=True,
        )

        # ── Step b: Reserve inventory stock ─────────────────────────────────
        reserve_resp = await client.post(
            f"{INVENTORY_URL}/data-products/stock-levels/reserve",
            json={"sku": req.sku, "quantity": req.quantity},
        )
        if reserve_resp.status_code == 404:
            raise HTTPException(status_code=400, detail=f"SKU '{req.sku}' not found")
        if reserve_resp.status_code == 409:
            raise HTTPException(
                status_code=409,
                detail=f"Insufficient stock for SKU '{req.sku}'",
            )
        if reserve_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Inventory service error")

        remaining = reserve_resp.json().get("remaining", "?")
        print(
            f"[ORDERS] Stock reserved — sku={req.sku} qty={req.quantity} "
            f"remaining={remaining}",
            flush=True,
        )

    # ── Step c: Persist the order ────────────────────────────────────────────
    order_id = "ORD-" + uuid.uuid4().hex[:8].upper()
    unit_price = _SKU_PRICE.get(req.sku, 0.0)
    total = round(unit_price * req.quantity, 2)
    order = db.insert(order_id, req.customer_id, req.sku, req.quantity, total)

    # ── Step d: Publish order.created event ──────────────────────────────────
    bus.publish("order.created", {
        "order_id": order_id,
        "customer_id": req.customer_id,
        "sku": req.sku,
        "quantity": req.quantity,
        "total": total,
    })

    return order


@app.get(
    "/data-products/revenue-summary",
    response_model=RevenueSummary,
    summary="Aggregated revenue metrics",
)
def revenue_summary():
    return db.revenue_summary()


@app.get("/health", summary="Health check")
def health():
    return {"status": "ok", "service": "orders", "domain": "orders"}
