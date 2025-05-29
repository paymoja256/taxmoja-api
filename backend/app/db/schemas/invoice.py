from typing import Optional, List
from app.db.schemas.core import CoreModel
from app.models.invoice import InvoiceStatuses


class InvoiceDetailsSchema(CoreModel):
    invoice_code: Optional[str] = ''
    cashier: str
    payment_mode: str
    currency: str
    invoice_type: str
    invoice_kind: str
    goods_description: str
    industry_code: Optional[str] = ''
    original_instance_invoice_id: Optional[str] = ''
    return_reason: Optional[str] = ''
    return_reason_code: Optional[str] = ''
    is_export: Optional[bool] = False

    class Config:
        from_attributes = True


class CreditNoteCancelSchema(CoreModel):
    original_invoice_id: str
    credit_note_fdn: str
    return_code: Optional[str] = '101'
    apply_category: Optional[str] = '104'

    class Config:
        from_attributes = True


class InvoiceGoodSchema(CoreModel):
    good_code: str
    quantity: float
    sale_price: float
    tax_category: Optional[str] = ''
    description: Optional[str] = ''

    class Config:
        from_attributes = True


class BuyerDetailsSchema(CoreModel):
    tax_pin: Optional[str] = ''
    nin: Optional[str] = ''
    passport_number: Optional[str] = ''
    legal_name: Optional[str] = ''
    business_name: Optional[str] = ''
    address: Optional[str] = ''
    email: Optional[str] = ''
    mobile: Optional[str] = ''
    buyer_type: str
    buyer_citizenship: Optional[str] = ''
    buyer_sector: Optional[str] = ''
    buyer_reference: Optional[str] = ''
    is_privileged: Optional[bool] = ''
    local_purchase_order: Optional[str] = ''

    class Config:
        from_attributes = True


class InvoiceAttachmentSchema(CoreModel):
    fileName: str
    fileType: str
    fileContent: str


class TaxInvoiceIncomingSchema(CoreModel):
    invoice_details: InvoiceDetailsSchema
    buyer_details: BuyerDetailsSchema
    goods_details: List[InvoiceGoodSchema]
    attachments: Optional[List[InvoiceAttachmentSchema]]=[]
    instance_invoice_id: str
    country_code: Optional[str] = 'UG'
    status: Optional[InvoiceStatuses] = 'RECEIVED'
    request_data: Optional[str] = ''

    class Config:
        from_attributes = True


class TaxInvoiceOutgoingSchema(CoreModel):
    invoice_code: Optional[str] = ''
    instance_invoice_id: str
    related_invoice: Optional[str] = ''
    client_tin: str
    request_data: str
    response_data: Optional[str] = ''
    country_code: str
    upload_code: Optional[str] = ''
    upload_desc: Optional[str] = ''
    status: InvoiceStatuses

    class Config:
        from_attributes = True


class InvoiceNumberSchema(CoreModel):
    invoice_code: str
    invoice_number: str
    tax_id: str
    invoice: Optional[str] = ''
    number_begin: Optional[str] = ''
    number_end: Optional[str] = ''

    class Config:
        from_attributes = True
