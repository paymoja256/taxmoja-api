from app.db.repositories.base import BaseRepository
from app.models.invoice import TaxInvoiceOutgoingBase, TaxInvoiceOutgoingInDB

CREATE_TAX_INVOICE_OUTGOING_QUERY = """INSERT INTO tax_invoice_outgoing (invoice_code, instance_invoice_id, 
related_invoice, client_tin,request_data,response_data,country_code,upload_code,upload_desc,status) VALUES (
:invoice_code, :instance_invoice_id, :related_invoice, :client_tin,:request_data,:response_data,:country_code,
:upload_code,:upload_desc,:status) RETURNING id, name, description, price, cleaning_type; """


class TaxInvoiceOutgoingRepository(BaseRepository):
    """"
    All database actions associated with the Cleaning resource
    """

    async def create_tax_invoice_outgoing(self, *, new_tax_invoice: TaxInvoiceOutgoingBase) -> TaxInvoiceOutgoingInDB:
        query_values = new_tax_invoice.dict()
        print(query_values)
        tax_invoice = await self.db.fetch_one(query=CREATE_TAX_INVOICE_OUTGOING_QUERY, values=query_values)
        return TaxInvoiceOutgoingInDB(**tax_invoice)
