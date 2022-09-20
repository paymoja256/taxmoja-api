import structlog

from app.api.handlers.invoice_handler import InvoiceHandler
from app.api.handlers.BJ.api import SfeInvoice

struct_logger = structlog.get_logger(__name__)


class TaxInvoiceHandler(InvoiceHandler):

    def __init__(self, settings):
        self.client = SfeInvoice(settings)
        self.ifu = settings["ifu"]

    async def _send_invoice(self, request_data):
        try:
            new_invoice = await self.client.send_invoice(request_data)

            struct_logger.info(event="_send_invoice",
                               api="BJ",
                               api_response=new_invoice,
                               )
            confirm_invoice = await self.client.confirm_invoice(new_invoice['uid'])
            struct_logger.info(event="_send_invoice",
                               api="BJ",
                               invoice_request=new_invoice,
                               invoice_confirmation=confirm_invoice,
                               data=request_data)
            return {**confirm_invoice, **new_invoice}
        except Exception as ex:

            return {"error": str(ex)}

    async def _confirm_invoice(self, uid):
        return await self.client.confirm_invoice(uid)

    async def _get_invoice_by_id(self, invoice_id):
        return await self.client.get_invoice_by_id(invoice_id)

    async def _get_all_invoices(self):
        return await self.client.get_all_invoices()

    async def _cancel_invoice(self, uid):
        return await self.client.cancel_invoice(uid)

    def convert_response(self, response):

        try:
            if response['qrCode']:
                self.generate_qr_code(response['qrCode'], 'BJ', self.ifu, response['uid'])
                return True, response
        except Exception:

            return False, response

    # TODO: use pydantic
    async def convert_request(self, db, invoice):
        items = []
        for item in invoice.goods_details:
            items.append({
                'name': item.good_code,
                'price': item.sale_price,
                'quantity': item.quantity,
                'taxGroup': item.tax_category
            })
        client = {
            'name': invoice.buyer_details.legal_name,
        }
        if invoice.buyer_details.mobile:
            client['contact'] = invoice.buyer_details.mobile,
        if invoice.buyer_details.tax_pin:
            client['ifu'] = invoice.buyer_details.tax_pin
        if invoice.buyer_details.address:
            client['address'] = invoice.buyer_details.address

        operator = {'name': invoice.invoice_details.cashier}

        request_dict = {
            'ifu': self.ifu,
            'shame': invoice.invoice_details.invoice_kind,
            'type': invoice.invoice_details.invoice_type,
            'items': items,
            'client': client,
            'operator': operator,
            'reference': invoice.invoice_details.original_instance_invoice_id
        }
        return request_dict
