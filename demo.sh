#!/usr/bin/env bash
# demo.sh — End-to-end Data Mesh demonstration
# Run after: docker compose up --build  (or start services manually)

set -euo pipefail

BASE_CATALOGUE="http://localhost:8000"
BASE_CUSTOMER="http://localhost:8001"
BASE_ORDERS="http://localhost:8002"
BASE_INVENTORY="http://localhost:8003"

# ── Colour helpers ────────────────────────────────────────────────────────────
BOLD="\033[1m"
CYAN="\033[36m"
GREEN="\033[32m"
YELLOW="\033[33m"
RESET="\033[0m"

hr()   { echo -e "${CYAN}────────────────────────────────────────────────────────────${RESET}"; }
step() { hr; echo -e "${BOLD}${GREEN} STEP $1: $2 ${RESET}"; hr; echo ""; }
info() { echo -e "${YELLOW}  ▶ $*${RESET}"; }

# ── Wait for services ─────────────────────────────────────────────────────────
wait_for() {
  local url="$1" label="$2"
  echo -n "  Waiting for $label ($url) "
  for _ in $(seq 1 30); do
    if curl -sf "$url" > /dev/null 2>&1; then
      echo -e " ${GREEN}ready${RESET}"
      return 0
    fi
    sleep 2
    echo -n "."
  done
  echo -e " ${YELLOW}TIMEOUT — continuing anyway${RESET}"
}

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║           Data Mesh Demo — End-to-End Scenario               ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${RESET}"
echo ""

info "Checking service readiness..."
wait_for "$BASE_CATALOGUE/health" "Data Catalogue (8000)"
wait_for "$BASE_CUSTOMER/health"  "Customer Domain  (8001)"
wait_for "$BASE_ORDERS/health"    "Orders Domain    (8002)"
wait_for "$BASE_INVENTORY/health" "Inventory Domain (8003)"
echo ""

# ── Step 1 ─────────────────────────────────────────────────────────────────────
step 1 "Discover all registered data products via the Data Catalogue"
info "GET $BASE_CATALOGUE/catalogue"
curl -s "$BASE_CATALOGUE/catalogue" | python -m json.tool
echo ""

# ── Step 2 ─────────────────────────────────────────────────────────────────────
step 2 "Check current inventory stock levels"
info "GET $BASE_INVENTORY/data-products/stock-levels"
curl -s "$BASE_INVENTORY/data-products/stock-levels" | python -m json.tool
echo ""

# ── Step 3 ─────────────────────────────────────────────────────────────────────
step 3 "Create an order: C001 buys 3 × SKU-A"
info "Flow:  customer validation → stock reservation → event bus publish"
info "POST $BASE_ORDERS/data-products/order-history"
curl -s -X POST "$BASE_ORDERS/data-products/order-history" \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "C001", "sku": "SKU-A", "quantity": 3}' \
  | python -m json.tool
echo ""

info "Place a large follow-up order to drive SKU-A below the low-stock threshold (5 units)..."
info "POST $BASE_ORDERS/data-products/order-history  [C002, SKU-A, qty=46]"
curl -s -X POST "$BASE_ORDERS/data-products/order-history" \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "C002", "sku": "SKU-A", "quantity": 46}' \
  | python -m json.tool
echo ""

# ── Step 4 ─────────────────────────────────────────────────────────────────────
step 4 "Check low-stock alerts — SKU-A should now be below threshold"
info "GET $BASE_INVENTORY/data-products/low-stock-alerts"
curl -s "$BASE_INVENTORY/data-products/low-stock-alerts" | python -m json.tool
echo ""

# ── Step 5 ─────────────────────────────────────────────────────────────────────
step 5 "Discover products tagged 'customer' via catalogue search"
info "GET $BASE_CATALOGUE/catalogue/search?q=customer"
curl -s "$BASE_CATALOGUE/catalogue/search?q=customer" | python -m json.tool
echo ""

# ── Bonus ──────────────────────────────────────────────────────────────────────
hr
echo -e "${BOLD}${CYAN}  BONUS: Additional endpoints${RESET}"
hr
echo ""

info "Customer segments (aggregated, no PII):"
curl -s "$BASE_CUSTOMER/data-products/customer-segments" | python -m json.tool
echo ""

info "Revenue summary after our orders:"
curl -s "$BASE_ORDERS/data-products/revenue-summary" | python -m json.tool
echo ""

info "Catalogue filter — inventory domain only:"
curl -s "$BASE_CATALOGUE/catalogue/inventory" | python -m json.tool
echo ""

info "Cross-domain health check:"
curl -s "$BASE_CATALOGUE/health/all" | python -m json.tool
echo ""

info "Create a brand-new customer (publishes customer.created event):"
curl -s -X POST "$BASE_CUSTOMER/data-products/customer-profiles" \
  -H "Content-Type: application/json" \
  -d '{"name": "Demo User", "email": "demo@datamesh.io", "segment": "premium"}' \
  | python -m json.tool
echo ""

hr
echo -e "${BOLD}  FastAPI Swagger UIs (open in browser):${RESET}"
echo -e "    Catalogue  →  ${CYAN}$BASE_CATALOGUE/docs${RESET}"
echo -e "    Customer   →  ${CYAN}$BASE_CUSTOMER/docs${RESET}"
echo -e "    Orders     →  ${CYAN}$BASE_ORDERS/docs${RESET}"
echo -e "    Inventory  →  ${CYAN}$BASE_INVENTORY/docs${RESET}"
hr
echo ""
