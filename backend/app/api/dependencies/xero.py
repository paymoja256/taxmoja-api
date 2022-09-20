import hashlib
import hmac
import base64
import json
import urllib

import requests
import structlog

from app.db.schemas.invoice import TaxInvoiceIncomingSchema, InvoiceDetailsSchema, InvoiceGoodSchema, BuyerDetailsSchema
from app.api.dependencies.efris_common import clean_currency, clean_buyer_type, clean_currency_product

struct_logger = structlog.get_logger(__name__)


class XeroHelper:
    def __init__(self, client_settings):
        self.xero_url = client_settings['xero_api_url']
        self.xero_tenant_id = client_settings['xero_tenant_id']
        self.xero_field_properties = client_settings['xero_field_properties']
        self.xero_client_id = client_settings['xero_client_id']
        self.xero_secret = client_settings['xero_secret']
        self.xero_invoice_webhook_key = client_settings['xero_invoice_webhook_key']
        self.xero_credentials = ''
        self.xero_oauth_client = ''
        self.xero_api_client = ''

    def validate_payload(self, payload):
        struct_logger.info(event="validating xero payload")
        data = payload.decode('utf8').replace("'", '"').replace("\\\\", '').replace("\\", '')
        struct_logger.info(event=data)
        data = json.loads(data)
        header_signature = data['signature']
        struct_logger.info(event=header_signature)
        payload_hashed = hmac.new(bytes(self.xero_invoice_webhook_key, 'utf8'), json.dumps(data['request_data']).encode('utf-8'), hashlib.sha256)
        generated_signature = base64.b64encode(payload_hashed.digest()).decode('utf8')
        struct_logger.info(event="validating xero payload",
                           payload_signature=generated_signature,
                           header_signature=header_signature,
                           data=data
                           )

        return header_signature == generated_signature

    def clean_incoming_invoice_schema(self, invoice_details, industry_code='101', invoice_type='1',
                                      invoice_kind='1', payment_mode='102'):
        data = json.loads(invoice_details.decode('utf8').replace("'", '"'))
        data = data['events'][0]
        invoice_id = data['resourceId']
        event_type = data['eventType']
        event_category = data['eventCategory']

        struct_logger.info(event="xero_incoming_invoice",
                           xero_data=data,
                           dt=type(data),
                           invoice_id=invoice_id,
                           event_type=event_type,
                           event_category=event_category
                           )

        xero_response = self.get_xero_invoice(invoice_id)

        struct_logger.info(event="xero_incoming_invoice_data",
                           xero_invoice_data=data,
                           xero_response=xero_response
                           )
        # if event_category in ('INVOICE'):
        #     try:
        #         # invoice_id = 541
        #         xero_response = self.get_xero_invoice(invoice_id)
        #
        #         struct_logger.info(event="xero_incoming_invoice_data",
        #                            xero_invoice_data=data,
        #                            xero_response=xero_response
        #                            )
        #
        #         # if event_type == 'DELETE':
        #         #     pass
        #         # elif event_type in ('CREATE'):
        #         #
        #         #     struct_logger.info(event="xero_incoming_invoice_schema",
        #         #                        message='INVOICE Create',
        #         #                        xero_invoice_data=xero_response
        #         #                        )
        #         #
        #         #     invoice_id = xero_response["ID"]
        #         #     cashier = xero_response["RESPONSIBLE_NAME"]
        #         #     currency = clean_currency(xero_response["CURRENCY"])
        #         #     products = xero_response["PRODUCT_ROWS"]
        #         #     goods_details = []
        #         #     buyer_details = xero_response["INVOICE_PROPERTIES"]
        #         #     buyer_type = clean_buyer_type(self.xero_field_properties["efris_buyer_type"])
        #         #     buyer_tin = clean_buyer_type(self.xero_field_properties["efris_buyer_tin"])
        #         #
        #         #     try:
        #         #         buyer_name = buyer_details["COMPANY"]
        #         #     except:
        #         #         buyer_name = buyer_details["FIO"]
        #         #
        #         #     if buyer_type in '0' and buyer_tin == "":
        #         #         return {"error_code": "invalid data", "msg": "tax pin required"}
        #         #     buyer_details = BuyerDetailsSchema(tax_pin=buyer_tin,
        #         #                                        nin="",
        #         #                                        passport_number="",
        #         #                                        legal_name=buyer_name,
        #         #                                        business_name=buyer_name,
        #         #                                        address="",
        #         #                                        email="",
        #         #                                        mobile="",
        #         #                                        buyer_type=buyer_type,
        #         #                                        buyer_citizenship="",
        #         #                                        buyer_sector="",
        #         #                                        buyer_reference=""
        #         #                                        )
        #         #     for product in products:
        #         #         good = InvoiceGoodSchema(good_code=product["ID"],
        #         #                                  quantity=product["QUANTITY"],
        #         #                                  sale_price=product["PRICE"])
        #         #
        #         #         goods_details.append(good)
        #         #
        #         #     incoming_invoice_schema = TaxInvoiceIncomingSchema(
        #         #         invoice_details=InvoiceDetailsSchema(
        #         #             invoice_code=invoice_id,
        #         #             cashier=cashier,
        #         #             payment_mode=payment_mode,
        #         #             currency=currency,
        #         #             invoice_type=invoice_type,
        #         #             invoice_kind=invoice_kind,
        #         #             goods_description=cashier,
        #         #             industry_code=industry_code
        #         #         ),
        #         #         instance_invoice_id=invoice_id,
        #         #         buyer_details=buyer_details,
        #         #         goods_details=goods_details
        #         #     )
        #         #
        #         #     struct_logger.info(event="xero_incoming_invoice",
        #         #                        invoice_schema=incoming_invoice_schema,
        #         #
        #         #                        )
        #         #
        #         #     return incoming_invoice_schema
        #     except Exception as ex:
        #         struct_logger.error(event="xero_incoming_invoice",
        #                             error=str(ex),
        #
        #                             )

    def clean_incoming_credit_note_schema(self, invoice_details):
        pass

    def get_xero_invoice(self, invoice_id):
        url = "http:/192.168.1.2:5000/get_invoice_data/?invoice_id={}".format(invoice_id)

        response = requests.request("GET", url)

        print(response.text)

        return response.json()
