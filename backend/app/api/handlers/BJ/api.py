from app.api.handlers.BJ.base import SfeBase


class SfeInvoice(SfeBase):

    async def heart_beat_request(self):
        response = await self.api_request('get', '')
        return response.text

    async def get_invoice_status(self):
        response = await self.api_request('get', 'api/info/status')
        return response.text

    async def get_tax_groups(self):
        response = await self.api_request('get', 'api/info/taxGroups')
        return response.json()

    async def get_invoice_types(self):
        response = await self.api_request('get', 'api/info/invoiceTypes')
        return response.json()

    async def get_payment_types(self):
        response = await self.api_request('get', 'api/info/paymentTypes')
        return response.json()

    async def get_all_invoices(self):
        response = await self.api_request('get', 'api/invoice', None)
        return response.text

    async def get_invoice_by_id(self, invoice_id):
        response = await self.api_request('get', 'api/invoice/{}'.format(invoice_id))
        return response.json()

    async def send_invoice(self, request_data):
        response = await self.api_request('post', 'api/invoice', request_data)
        return response.json()

    async def confirm_invoice(self, uid):

        response = await self.api_request('put', 'api/invoice/{}/confirm'.format(uid))
        return response.json()

    async def cancel_invoice(self, uid):
        response = await self.api_request('put', 'api/invoice/{}/cancel'.format(uid))
        return response.json()

    # TODO: use pydantic
    def convert_invoice_to_json(self, invoice):
        # takes an Invoice objects and creates the DTO
        # json out of it

        # items
        items = []
        for item in invoice.goods_details:
            items.append({
                'name': item.good_code,
                'price': item.sale_price,
                'quantity': item.quantity,
                'taxGroup': item.tax_category
            })

        # customer details are OPTIONAL
        # so don't send any more than necessarry
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
            'type': invoice.invoice_details.invoice_type,
            'items': items,
            'client': client,
            'operator': operator
        }
        return request_dict


