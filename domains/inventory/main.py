"""Inventory Domain — owns stock levels and low-stock alert data products."""

import os
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator, List

from fastapi import FastAPI, HTTPException

# ── Resolve shared event_bus package ─────────────────────────────────────────
_here = os.path.dirname(os.path.abspath(__file__))
_platform = os.path.abspath(os.path.join(_here, "../../platform"))
if _platform not in sys.path:
    sys.path.insert(0, _platform)

from event_bus.bus import EventBus  # noqa: E402

import catalogue  # noqa: E402
import db  # noqa: E402
from models import LowStockAlert, Product, StockReserveRequest  # noqa: E402


# ── Event handlers ────────────────────────────────────────────────────────────

def _handle_order_created(payload: dict) -> None:
    """
    In-process handler subscribed to 'order.created'.

    Within a single process this fires immediately when the event is published
    (e.g. during integration tests or a monolith run).  In Docker the bus is
    per-container, so the /reserve endpoint publishes the event locally to
    trigger this same handler — demonstrating the intra-service pattern.
    """
    sku = payload.get("sku")
    qty = payload.get("quantity", 0)
    print(f"[INVENTORY] order.created received — sku={sku} qty={qty}", flush=True)

    # Check whether the reservation pushed us below threshold
    product = db.get_product(sku) if sku else None
    if product and product["stock_qty"] < product["threshold"]:
        bus.publish("inventory.low", {
            "sku": sku,
            "stock_qty": product["stock_qty"],
            "threshold": product["threshold"],
            "deficit": product["threshold"] - product["stock_qty"],
        })


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db.init_db()
    db.seed()
    await catalogue.register_products()
    # Subscribe to the local in-process event bus
    bus.subscribe("order.created", _handle_order_created)
    yield


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Inventory Domain",
    description="Owns stock levels and inventory management data products.",
    version="1.0.0",
    lifespan=lifespan,
)

bus = EventBus.get_instance()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get(
    "/data-products/stock-levels",
    response_model=List[Product],
    summary="List current stock levels for all SKUs",
)
def list_stock():
    return db.get_all_products()


@app.get(
    "/data-products/stock-levels/{sku}",
    response_model=Product,
    summary="Get stock level for a specific SKU",
)
def get_stock(sku: str):
    product = db.get_product(sku)
    if not product:
        raise HTTPException(status_code=404, detail=f"SKU '{sku}' not found")
    return product


@app.post(
    "/data-products/stock-levels/reserve",
    summary="Reserve (decrement) stock for an order — called by the Orders domain",
)
def reserve_stock(req: StockReserveRequest):
    result = db.reserve_stock(req.sku, req.quantity)

    if result["reason"] == "not_found":
        raise HTTPException(status_code=404, detail=f"SKU '{req.sku}' not found")
    if result["reason"] == "insufficient":
        raise HTTPException(
            status_code=409,
            detail=f"Insufficient stock for SKU '{req.sku}'",
        )

    product = result["product"]

    # Publish order.created to the LOCAL bus so _handle_order_created fires.
    # This mirrors what the Orders domain publishes on its own bus —
    # demonstrating the intra-service event pattern even in Docker.
    bus.publish("order.created", {
        "sku": req.sku,
        "quantity": req.quantity,
        "source": "http_reserve",
    })

    return {
        "status": "reserved",
        "sku": req.sku,
        "quantity": req.quantity,
        "remaining": product["stock_qty"],
    }


@app.get(
    "/data-products/low-stock-alerts",
    response_model=List[LowStockAlert],
    summary="List products currently below their reorder threshold",
)
def low_stock_alerts():
    items = db.get_low_stock()
    return [
        LowStockAlert(
            sku=item["sku"],
            name=item["name"],
            stock_qty=item["stock_qty"],
            threshold=item["threshold"],
            deficit=item["threshold"] - item["stock_qty"],
        )
        for item in items
    ]


@app.get("/health", summary="Health check")
def health():
    return {"status": "ok", "service": "inventory", "domain": "inventory"}
