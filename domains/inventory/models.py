from pydantic import BaseModel


class Product(BaseModel):
    sku: str
    name: str
    stock_qty: int
    threshold: int


class StockReserveRequest(BaseModel):
    sku: str
    quantity: int


class LowStockAlert(BaseModel):
    sku: str
    name: str
    stock_qty: int
    threshold: int
    deficit: int
