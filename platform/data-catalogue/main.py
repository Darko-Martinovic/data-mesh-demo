"""Data Catalogue — central registry for all domain data products."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import store

# ── Templates ──────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ── URL Helpers ────────────────────────────────────────────────────────────────

SERVICE_PORT_MAP = {
    "catalogue": "8000",
    "customer": "8001",
    "orders": "8002",
    "inventory": "8003",
}


def _to_localhost_url(url: str) -> str:
    """Convert internal container URLs to localhost URLs for browser access."""
    for service, port in SERVICE_PORT_MAP.items():
        pattern = rf"http://{service}:\d+"
        if re.search(pattern, url):
            return re.sub(pattern, f"http://localhost:{port}", url)
    return url


DOMAIN_COLORS = {
    "customer": {
        "border": "border-blue-500",
        "label_bg": "bg-blue-100",
        "label_text": "text-blue-800",
    },
    "orders": {
        "border": "border-purple-500",
        "label_bg": "bg-purple-100",
        "label_text": "text-purple-800",
    },
    "inventory": {
        "border": "border-green-500",
        "label_bg": "bg-green-100",
        "label_text": "text-green-800",
    },
}

DEFAULT_DOMAIN_COLOR = {
    "border": "border-gray-500",
    "label_bg": "bg-gray-100",
    "label_text": "text-gray-800",
}


def _externalize_product(product: dict) -> dict:
    """Convert product endpoint to browser-accessible URL and add domain colors."""
    p = dict(product)
    p["endpoint"] = _to_localhost_url(p["endpoint"])
    colors = DOMAIN_COLORS.get(p["domain"], DEFAULT_DOMAIN_COLOR)
    p["label_bg"] = colors["label_bg"]
    p["label_text"] = colors["label_text"]
    return p


# ── Schema ─────────────────────────────────────────────────────────────────────

class DataProduct(BaseModel):
    name: str
    domain: str
    description: str
    version: str
    endpoint: str
    tags: List[str]
    owner: str
    sla: Dict[str, str]
    schema_definition: Dict[str, Any]


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Data Catalogue",
    description="Central registry: discover, register, and monitor data products across all domains.",
    version="1.0.0",
)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/catalogue/register", status_code=201, summary="Register or update a data product")
def register_product(product: DataProduct):
    stored = store.register(product.model_dump())
    return {"status": "registered", "product": stored}


@app.get("/catalogue", summary="List all registered data products")
def list_catalogue():
    return store.list_all()


@app.get("/catalogue/search", summary="Full-text search across name, description, and tags")
def search_catalogue(q: str = Query("", description="Keyword to search")):
    return store.search(q)


@app.get("/catalogue/{domain}", summary="List data products for a specific domain")
def list_by_domain(domain: str):
    products = store.list_by_domain(domain)
    if not products:
        raise HTTPException(status_code=404, detail=f"No products found for domain '{domain}'")
    return products


@app.get("/health/all", summary="Ping /health on every registered domain")
async def health_all():
    products = store.list_all()
    results: Dict[str, Any] = {}
    seen: set = set()

    async with httpx.AsyncClient(timeout=5.0) as client:
        for product in products:
            # Strip to base URL (everything before /data-products)
            base = product["endpoint"].split("/data-products")[0]
            if base in seen:
                continue
            seen.add(base)
            domain = product["domain"]
            try:
                resp = await client.get(f"{base}/health")
                results[domain] = {
                    "status": "ok" if resp.status_code == 200 else "degraded",
                    "http_status": resp.status_code,
                    "url": f"{base}/health",
                }
            except Exception as exc:
                results[domain] = {"status": "unreachable", "error": str(exc)}

    return {"services": results, "checked": len(seen)}


@app.get("/health", summary="Catalogue health check")
def health():
    return {"status": "ok", "service": "data-catalogue"}


# ── UI Routes ──────────────────────────────────────────────────────────────────


async def _get_health_data() -> Dict[str, Any]:
    """Fetch health status for all registered services."""
    products = store.list_all()
    results: Dict[str, Any] = {}
    seen: set = set()

    async with httpx.AsyncClient(timeout=5.0) as client:
        for product in products:
            base = product["endpoint"].split("/data-products")[0]
            if base in seen:
                continue
            seen.add(base)
            domain = product["domain"]
            external_url = _to_localhost_url(f"{base}/health")
            try:
                resp = await client.get(f"{base}/health")
                results[domain] = {
                    "status": "ok" if resp.status_code == 200 else "degraded",
                    "http_status": resp.status_code,
                    "url": external_url,
                }
            except Exception as exc:
                results[domain] = {"status": "unreachable", "error": str(exc), "url": external_url}

    return results


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def ui_home(request: Request):
    """Dashboard homepage."""
    products = store.list_all()
    health_data = await _get_health_data()

    domains_map: Dict[str, Dict] = {}
    for p in products:
        d = p["domain"]
        if d not in domains_map:
            domains_map[d] = {
                "name": d,
                "products": [],
                "product_count": 0,
                "healthy": True,
                "color": DOMAIN_COLORS.get(d, "border-gray-500"),
            }
        domains_map[d]["products"].append(p["name"])
        domains_map[d]["product_count"] += 1
        if d in health_data and health_data[d].get("status") != "ok":
            domains_map[d]["healthy"] = False

    healthy_count = sum(1 for s in health_data.values() if s.get("status") == "ok")
    unhealthy_count = len(health_data) - healthy_count

    stats = {
        "total_products": len(products),
        "total_domains": len(domains_map),
        "healthy_services": healthy_count,
        "unhealthy_services": unhealthy_count,
    }

    return templates.TemplateResponse("index.html", {
        "request": request,
        "active_page": "home",
        "stats": stats,
        "domains": list(domains_map.values()),
        "products": [_externalize_product(p) for p in products],
    })


@app.get("/ui/catalogue", response_class=HTMLResponse, include_in_schema=False)
async def ui_catalogue(
    request: Request,
    domain: Optional[str] = None,
    q: Optional[str] = None,
):
    """Browse and search data products."""
    products = store.list_all()

    if domain:
        products = [p for p in products if p["domain"] == domain]

    if q:
        q_lower = q.lower()
        products = [
            p for p in products
            if q_lower in p["name"].lower()
            or q_lower in p["description"].lower()
            or any(q_lower in tag.lower() for tag in p.get("tags", []))
        ]

    all_domains = sorted(set(p["domain"] for p in store.list_all()))

    return templates.TemplateResponse("catalogue.html", {
        "request": request,
        "active_page": "catalogue",
        "products": [_externalize_product(p) for p in products],
        "domains": all_domains,
        "current_domain": domain,
        "search_query": q,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    })


@app.get("/ui/product/{domain}/{name}", response_class=HTMLResponse, include_in_schema=False)
async def ui_product_detail(request: Request, domain: str, name: str):
    """View a single data product's details."""
    products = store.list_all()
    product = next((p for p in products if p["domain"] == domain and p["name"] == name), None)

    if not product:
        raise HTTPException(status_code=404, detail="Data product not found")

    ext_product = _externalize_product(product)
    schema_json = json.dumps(product.get("schema_definition", {}), indent=2)

    return templates.TemplateResponse("product.html", {
        "request": request,
        "active_page": "catalogue",
        "product": ext_product,
        "schema_json": schema_json,
    })


@app.get("/ui/health", response_class=HTMLResponse, include_in_schema=False)
async def ui_health(request: Request):
    """Service health dashboard."""
    services = await _get_health_data()
    all_healthy = all(s.get("status") == "ok" for s in services.values())
    unhealthy_count = sum(1 for s in services.values() if s.get("status") != "ok")

    return templates.TemplateResponse("health.html", {
        "request": request,
        "active_page": "health",
        "services": services,
        "all_healthy": all_healthy,
        "unhealthy_count": unhealthy_count,
        "last_check": datetime.now().strftime("%H:%M:%S"),
    })


@app.get("/ui/partials/health-status", response_class=HTMLResponse, include_in_schema=False)
async def ui_health_partial(request: Request):
    """HTMX partial for health status cards."""
    services = await _get_health_data()
    return templates.TemplateResponse("partials/health_cards.html", {
        "request": request,
        "services": services,
    })


@app.get("/ui/partials/catalogue-content", response_class=HTMLResponse, include_in_schema=False)
async def ui_catalogue_partial(
    request: Request,
    domain: Optional[str] = None,
    q: Optional[str] = None,
):
    """HTMX partial for catalogue product grid (auto-refresh)."""
    products = store.list_all()

    if domain:
        products = [p for p in products if p["domain"] == domain]

    if q:
        q_lower = q.lower()
        products = [
            p for p in products
            if q_lower in p["name"].lower()
            or q_lower in p["description"].lower()
            or any(q_lower in tag.lower() for tag in p.get("tags", []))
        ]

    return templates.TemplateResponse("partials/catalogue_content.html", {
        "request": request,
        "products": [_externalize_product(p) for p in products],
        "current_domain": domain,
        "search_query": q,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    })
