"""JSON-backed product registry with thread-safe reads and writes."""

import json
import os
import threading
from typing import Any, Dict, List

_CATALOGUE_FILE = os.environ.get("CATALOGUE_FILE", "catalogue.json")
_lock = threading.Lock()


# ── Persistence helpers ───────────────────────────────────────────────────────

def _load() -> List[Dict[str, Any]]:
    if not os.path.exists(_CATALOGUE_FILE):
        return []
    with open(_CATALOGUE_FILE) as f:
        return json.load(f)


def _save(products: List[Dict[str, Any]]) -> None:
    with open(_CATALOGUE_FILE, "w") as f:
        json.dump(products, f, indent=2)


# ── Public API ────────────────────────────────────────────────────────────────

def register(product: Dict[str, Any]) -> Dict[str, Any]:
    """Upsert a data product entry (matched by name + domain)."""
    with _lock:
        products = _load()
        for i, p in enumerate(products):
            if p["name"] == product["name"] and p["domain"] == product["domain"]:
                products[i] = product
                _save(products)
                return product
        products.append(product)
        _save(products)
    return product


def list_all() -> List[Dict[str, Any]]:
    return _load()


def list_by_domain(domain: str) -> List[Dict[str, Any]]:
    return [p for p in _load() if p["domain"].lower() == domain.lower()]


def search(q: str) -> List[Dict[str, Any]]:
    q_lower = q.lower()
    return [
        p for p in _load()
        if q_lower in p["name"].lower()
        or q_lower in p.get("description", "").lower()
        or any(q_lower in tag.lower() for tag in p.get("tags", []))
    ]
