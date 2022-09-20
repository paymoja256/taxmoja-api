from pydantic import BaseModel


class DearProductBase(BaseModel):
    productID: str
    productSKU: str
    productName: str
    PriceTierName: str
    Price: str


class DearStockBase(BaseModel):
    ID: str = None
    SKU: str = None
    Name: str = None
    Barcode: str = None
    Location: str = None
    Bin: str = None
    Batch: str = None
    ExpiryDate: str = None
    Category: str = None
    OnHand: str = None
    Allocated: str = None
    Available: str = None
    OnOrder: str = None
    StockOnHand: str = None
    MaxRows: str = None
