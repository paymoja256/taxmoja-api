from app.api.handlers.BJ.api import SfeInvoice
from app.api.handlers.information_handler import InformationHandler


class TaxInformationHandler(InformationHandler):

    def __init__(self, settings):
        self.client = SfeInvoice(settings)

    async def get_invoice_status(self):
        return await self.client.get_invoice_status()

    async def get_tax_groups(self):
        return await self.client.get_tax_groups()

    async def get_invoice_types(self):
        return await self.client.get_invoice_types()

    async def get_payment_types(self):
        return await self.client.get_payment_types()

    async def get_all_invoice(self):
        return await self.client.get_all_invoices()

    async def heart_beat_request(self):
        return await self.client.heart_beat_request()

    def convert_response(self, response):
        return True, response
