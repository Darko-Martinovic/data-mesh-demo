from pydantic import BaseModel
from typing import Dict


class Order(BaseModel):
    id: str
    customer_id: str
    sku: str
    quantity: int
    total: float
    status: str
    created_at: str


class CreateOrderRequest(BaseModel):
    customer_id: str
    sku: str
    quantity: int


class RevenueSummary(BaseModel):
    total_revenue: float
    total_orders: int
    average_order_value: float
    by_sku: Dict
