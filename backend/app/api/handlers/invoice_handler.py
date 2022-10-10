import pyqrcode
import structlog
from fastapi import Depends
from pydantic import parse_obj_as
from app.models.invoice import TaxInvoiceOutgoing, InvoiceStatuses
from app.db.schemas.invoice import TaxInvoiceIncomingSchema
from app.models.invoice_dal import save_invoice, create_outgoing_invoice, get_invoice
import simplejson as json
from app.api.dependencies.database import get_database

struct_logger = structlog.get_logger(__name__)


class InvoiceHandler:
    '''
    Base class for integrations with tax services
    that involve sending invoices
    '''

    def __init__(self, settings):
        """
        Usually, some settings will be needed to initialize a client
        """
        self.country_code = ''
        self.tax_id = ''

    def create_outgoing_invoice(self,
                                db,
                                tax_invoice: TaxInvoiceIncomingSchema,
                                country_code,
                                tax_id):
        message, new_invoice = create_outgoing_invoice(db,
                                                       tax_invoice,
                                                       country_code,
                                                       tax_id)

        struct_logger.info(event='create_outgoing_invoice',
                           message=message,
                           invoice=new_invoice.instance_invoice_id,
                           invoice_status=new_invoice.status
                           )
        return new_invoice

    async def send_invoice(self, db, invoice: TaxInvoiceOutgoing):
        """
        Sends the invoice to the RA, using
        1. converts request_data to format the RA expects
        2. saves the response
        3. updates the invoice status
        """

        struct_logger.info(event='sending_incoming_invoice',
                           message="processing received invoice",
                           invoice=invoice.instance_invoice_id,
                           status = invoice.status

                           )

        if invoice.status == InvoiceStatuses.RECEIVED:
            try:
                request_invoice = invoice.request_invoice or parse_obj_as(TaxInvoiceIncomingSchema,
                                                                          json.loads(invoice.request_data))
                
            except:
                request_invoice = json.loads(invoice.request_data)
                struct_logger.info(event='sending_incoming_invoice',
                                   message=request_invoice.instance_invoice_id
                                   )
                
            struct_logger.info(event='sending_incoming_invoice',
                           message="sending new invoice",
                           invoice=invoice.instance_invoice_id,
                           status = invoice.response_data
                           )
            request_data = await self.convert_request(db, request_invoice)
            if invoice.request_data:
                invoice.request_data = request_data
                invoice.status = InvoiceStatuses.SENDING
            else:
                invoice.status = InvoiceStatuses.ERROR
                return "There was an error with the request data"

        elif invoice.status == InvoiceStatuses.SENT:
            """ZRA blocks if invoice number is sent twice"""
            struct_logger.info(event='sending_incoming_invoice',
                           message="invoice already sent",
                           invoice=invoice.instance_invoice_id,
                           status = invoice.response_data
                           )

            return invoice

        else:
            struct_logger.info(event='sending_incoming_invoice',
                           message="resending incoming invoice",
                           invoice=invoice.instance_invoice_id,
                           status = invoice.request_data
                           )

            request_data = invoice.request_data
            await self.client.get_key_signature()

        api_response = await self._send_invoice(request_data)

        struct_logger.info(event='EFRIS invoice handler',
                           message="Invoice sent to api",
                           response=api_response
                           )
        success, response_data = self.convert_response(api_response)

        struct_logger.info(event='Invoice handler',
                           message="sending invoice upload request",
                           status=success,
                           response=api_response
                           )

        invoice.status = InvoiceStatuses.SENT if success else InvoiceStatuses.ERROR

        invoice.response_data = response_data
        save_invoice(db, invoice)

        return invoice.response_data

    async def convert_request(self, db, request_invoice: TaxInvoiceIncomingSchema):
        '''
        Takes a TaxInvoiceOutgoing and converts it to
        the representation the client expects. 
        '''
        return request_invoice

    def convert_response(self, response):
        '''
        From the response, determine if the invoice request was successful
        And, if necessarry, convert the response data to json to save in
        response_data
        '''
        return True, response

    async def get_invoice_status(self, instance_invoice_id):

        """Get invoice status from database"""
        pass

    async def cancel_invoice(self, tax_invoice):

        """Get invoice status from database"""
        pass

    @staticmethod
    async def get_invoice_by_id(db,
                                instance_invoice_id,
                                country_code,
                                tax_id):

        """Get invoice from database"""

        return get_invoice(db, instance_invoice_id, country_code, tax_id)

    async def _get_all_invoices(self):

        """Get invoice all invoices from database"""
        raise NotImplementedError

    async def _send_invoice(self, request_data):
        '''
        Actually send the invoice
        '''
        raise NotImplementedError

    def _print_invoice(self, invoice_code):

        raise NotImplementedError

    def generate_qr_code(self, qr_text, country_code, tax_pin, qr_name):
        qr_code = pyqrcode.create(qr_text)
        qr_code.png("app/api/static/qr_codes/{}/{}/{}.png".format(country_code, tax_pin, qr_name),
                    scale=2)
