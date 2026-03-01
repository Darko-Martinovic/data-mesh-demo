from enum import Enum
from pydantic import BaseModel


class CustomerSegment(str, Enum):
    PREMIUM = "premium"
    STANDARD = "standard"
    BASIC = "basic"


class Customer(BaseModel):
    id: str
    name: str
    email: str
    segment: str
    status: str
    created_at: str


class CreateCustomerRequest(BaseModel):
    name: str
    email: str
    segment: CustomerSegment = CustomerSegment.STANDARD
