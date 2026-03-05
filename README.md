# Data Mesh Demo

A runnable three-domain Data Mesh built with **FastAPI + SQLite + asyncio**.

```
                        ┌─────────────────────────────┐
                        │     Data Catalogue  :8000    │
                        │  Central registry & health   │
                        └──────────┬──────────────────-┘
                      register on  │  register on startup
                         startup   │
            ┌──────────────────────┼────────────────────────┐
            │                      │                         │
    ┌───────┴──────┐    ┌──────────┴────────┐    ┌──────────┴──────┐
    │  Customer    │    │     Orders        │    │   Inventory     │
    │   :8001      │◄───┤     :8002         ├───►│    :8003        │
    │              │    │                   │    │                 │
    │ • profiles   │    │ • order-history   │    │ • stock-levels  │
    │ • segments   │    │ • revenue-summary │    │ • low-stock     │
    └──────────────┘    └───────────────────┘    └─────────────────┘

       HTTP GET ───►   HTTP POST /reserve ───►
       (customer        (inventory decrements
        validation)      stock + fires event)
```

## Data Mesh Principles Demonstrated

Data Mesh defines **four core principles** (Zhamak Dehghani, 2019):

| Principle | How it is shown |
|---|---|
| **1. Domain ownership** | Each service owns its own SQLite DB, models, and API surface |
| **2. Data as a product** | Every endpoint is a named, versioned *data product* with an SLA and schema |
| **3. Self-serve data platform** | Data Catalogue lets any domain register and discover products at runtime |
| **4. Federated computational governance** | PII masking policy enforced at the domain boundary (Customer service) |

### Bonus: Architectural Patterns

| Pattern | How it is shown |
|---|---|
| **Event-driven decoupling** | `EventBus` pub/sub within each service; `order.created` / `inventory.low` events |

> **Note:** Event-driven architecture is not a Data Mesh principle — it's an implementation pattern that supports loose coupling between domains.

---

## Quick Start — Docker

```bash
cd data-mesh-demo
docker compose up --build
```

All four services start in dependency order (catalogue first, then the three domains).
Each domain registers its data products in the catalogue on startup.

Run the end-to-end demo:

```bash
chmod +x demo.sh
./demo.sh
```

---

## Quick Start — Without Docker

Install dependencies and start each service in a separate terminal:

```bash
# Terminal 1 — Data Catalogue
cd platform/data-catalogue
pip install -r requirements.txt
uvicorn main:app --port 8000

# Terminal 2 — Customer Domain
cd domains/customer
pip install -r requirements.txt
uvicorn main:app --port 8001

# Terminal 3 — Orders Domain
cd domains/orders
pip install -r requirements.txt
uvicorn main:app --port 8002

# Terminal 4 — Inventory Domain
cd domains/inventory
pip install -r requirements.txt
uvicorn main:app --port 8003
```

> **Note:** run services from *inside* each domain directory so SQLite files are created
> in the right place and the event_bus path resolution finds `../../platform`.

---

## FastAPI Auto-Docs

| Service | URL |
|---|---|
| Data Catalogue | http://localhost:8000/docs |
| Customer Domain | http://localhost:8001/docs |
| Orders Domain | http://localhost:8002/docs |
| Inventory Domain | http://localhost:8003/docs |

---

## Sample curl Commands

### Data Catalogue

```bash
# List all registered data products
curl http://localhost:8000/catalogue

# Filter by domain
curl http://localhost:8000/catalogue/customer
curl http://localhost:8000/catalogue/orders
curl http://localhost:8000/catalogue/inventory

# Keyword search (name, description, tags)
curl "http://localhost:8000/catalogue/search?q=analytics"
curl "http://localhost:8000/catalogue/search?q=customer"

# Ping /health on every domain
curl http://localhost:8000/health/all
```

### Customer Domain

```bash
# List all profiles (email masked by default)
curl http://localhost:8001/data-products/customer-profiles

# Unmask PII
curl "http://localhost:8001/data-products/customer-profiles?unmasked=true"

# Single customer
curl http://localhost:8001/data-products/customer-profiles/C001

# Create a new customer (publishes customer.created event)
curl -X POST http://localhost:8001/data-products/customer-profiles \
  -H "Content-Type: application/json" \
  -d '{"name": "Jane Doe", "email": "jane@example.com", "segment": "premium"}'

# Aggregated segments
curl http://localhost:8001/data-products/customer-segments
```

### Orders Domain

```bash
# List all orders
curl http://localhost:8002/data-products/order-history

# Get single order
curl http://localhost:8002/data-products/order-history/ORD-XXXXXXXX

# Create order — triggers: customer check → stock reserve → event publish
curl -X POST http://localhost:8002/data-products/order-history \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "C001", "sku": "SKU-A", "quantity": 3}'

# Error: unknown customer
curl -X POST http://localhost:8002/data-products/order-history \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "C999", "sku": "SKU-A", "quantity": 1}'

# Error: insufficient stock
curl -X POST http://localhost:8002/data-products/order-history \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "C001", "sku": "SKU-A", "quantity": 9999}'

# Revenue summary
curl http://localhost:8002/data-products/revenue-summary
```

### Inventory Domain

```bash
# All stock levels
curl http://localhost:8003/data-products/stock-levels

# Single SKU
curl http://localhost:8003/data-products/stock-levels/SKU-A

# Reserve stock directly (normally called by Orders)
curl -X POST http://localhost:8003/data-products/stock-levels/reserve \
  -H "Content-Type: application/json" \
  -d '{"sku": "SKU-B", "quantity": 5}'

# Low-stock alerts (products below threshold)
curl http://localhost:8003/data-products/low-stock-alerts
```

---

## Demo Scenario Walkthrough

The `demo.sh` script executes this flow automatically:

```
Step 1  GET  /catalogue                     → show all 6 registered data products
Step 2  GET  /stock-levels                  → initial state: SKU-A…E each at qty=50
Step 3  POST /order-history  qty=3          → customer check → reserve → event
        POST /order-history  qty=46         → deplete SKU-A below threshold=5
Step 4  GET  /low-stock-alerts              → SKU-A now at qty=1, deficit=4
Step 5  GET  /catalogue/search?q=customer   → discover customer-tagged products
Bonus   segments / revenue / health-all
```

**Event flow for POST /order-history:**

```
Orders domain
  │  GET /customer-profiles/{id}  ──►  Customer domain (validate)
  │  POST /stock-levels/reserve   ──►  Inventory domain (atomic decrement)
  │                                       │  bus.publish("order.created", …)
  │                                       │  _handle_order_created()
  │                                       │    stock_qty < threshold?
  │                                       └──► bus.publish("inventory.low", …)
  │  bus.publish("order.created", …)
  └─►  [EVENT BUS] timestamp | order.created | {order_id, customer_id, sku, …}
```

The `EventBus` is an **in-process** singleton per service (asyncio + threading).
Cross-service calls use plain HTTP (`httpx.AsyncClient`).  The `/reserve` endpoint
in the inventory service also fires `order.created` on its own local bus so the
`_handle_order_created` subscriber and the `inventory.low` event are always
demonstrated regardless of whether the services share a process.

---

## Project Layout

```
data-mesh-demo/
  platform/
    event_bus/
      bus.py            ← Singleton EventBus (asyncio.Queue + threading)
    data-catalogue/     ← Port 8000
      main.py           ← FastAPI app: register / list / search / health-all
      store.py          ← JSON-backed persistence (catalogue.json)
      requirements.txt
      Dockerfile
  domains/
    customer/           ← Port 8001
      main.py           ← REST endpoints + PII masking + event publish
      db.py             ← SQLite helpers (customers table, 10 seed rows)
      models.py         ← Pydantic schemas
      catalogue.py      ← Startup registration logic
      requirements.txt
      Dockerfile
    orders/             ← Port 8002  (same structure)
    inventory/          ← Port 8003  (same structure)
  docker-compose.yml
  demo.sh               ← End-to-end curl walkthrough
  README.md
```

---

## Seeded Data

**Customers** (C001–C010) — 3 premium, 4 standard, 3 basic
**SKUs** — SKU-A through SKU-E, each starting at qty=50, threshold=5
**Prices** — SKU-A $29.99 · SKU-B $49.99 · SKU-C $19.99 · SKU-D $99.99 · SKU-E $14.99
