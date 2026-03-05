"""Customer Domain — owns customer identity and segmentation data products."""

import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator, List

from fastapi import FastAPI, HTTPException, Query

from event_bus.bus import EventBus
import catalogue
import db
from models import CreateCustomerRequest, Customer


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db.init_db()
    db.seed()
    await catalogue.register_products()
    yield


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Customer Domain",
    description="Owns customer identity and segmentation data products.",
    version="1.0.0",
    lifespan=lifespan,
)

bus = EventBus.get_instance()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _mask_email(email: str) -> str:
    user, _, domain = email.partition("@")
    return f"{user[:1]}***@{domain}" if domain else "***"


def _fmt(customer: dict, unmasked: bool) -> dict:
    c = dict(customer)
    if not unmasked:
        c["email"] = _mask_email(c["email"])
    return c


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get(
    "/data-products/customer-profiles",
    response_model=List[Customer],
    summary="List all customer profiles (email masked by default)",
)
def list_customers(unmasked: bool = Query(False, description="Return real email addresses")):
    return [_fmt(c, unmasked) for c in db.get_all()]


@app.get(
    "/data-products/customer-profiles/{customer_id}",
    response_model=Customer,
    summary="Get a single customer profile",
)
def get_customer(customer_id: str, unmasked: bool = Query(False)):
    customer = db.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return _fmt(customer, unmasked)


@app.post(
    "/data-products/customer-profiles",
    response_model=Customer,
    status_code=201,
    summary="Create a new customer (publishes customer.created event)",
)
def create_customer(req: CreateCustomerRequest):
    customer_id = "C" + uuid.uuid4().hex[:8].upper()
    customer = db.insert(customer_id, req.name, req.email, req.segment.value)
    bus.publish("customer.created", {
        "customer_id": customer["id"],
        "name": customer["name"],
        "segment": customer["segment"],
    })
    return _fmt(customer, unmasked=False)


@app.get(
    "/data-products/customer-segments",
    summary="Aggregated breakdown of customers by segment",
)
def customer_segments():
    customers = db.get_all()
    total = len(customers)
    counts: dict = {}
    for c in customers:
        counts[c["segment"]] = counts.get(c["segment"], 0) + 1
    return [
        {
            "segment": seg,
            "count": cnt,
            "percentage": round(cnt / total * 100, 1) if total else 0.0,
        }
        for seg, cnt in sorted(counts.items())
    ]


@app.get("/health", summary="Health check")
def health():
    return {"status": "ok", "service": "customer", "domain": "customer"}
