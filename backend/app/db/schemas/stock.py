from typing import Optional
from app.db.schemas.core import CoreModel
from app.models.invoice import InvoiceStatuses


class IncomingStockConfigurationSchema(CoreModel):
    goods_name: str
    goods_code: str
    unit_price: str
    measure_unit: str
    currency: str
    commodity_tax_category: str
    goods_description: str
    status: Optional[InvoiceStatuses]

    class Config:
        orm_mode = True


class IncomingGoodsStockAdjustmentSchema(CoreModel):
    goods_code: str
    supplier: Optional[str] = ''
    supplier_tin: Optional[str] = ''
    stock_in_type:  Optional[str] = ''
    quantity: str
    purchase_price: str
    purchase_remarks: str
    operation_type: str
    adjust_type: Optional[str] = ''

    class Config:
        orm_mode = True


class BranchSchema(CoreModel):
    client_id: str
    branch_name: str
    branch_id: str

    class Config:
        orm_mode = True
