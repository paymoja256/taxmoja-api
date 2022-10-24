import urllib
import structlog
from bitrix24 import *

from app.db.schemas.stock import IncomingStockConfigurationSchema, IncomingGoodsStockAdjustmentSchema
from app.db.schemas.invoice import TaxInvoiceIncomingSchema, InvoiceDetailsSchema, InvoiceGoodSchema, BuyerDetailsSchema
from app.api.dependencies.common import clean_currency, clean_buyer_type, clean_currency_product

struct_logger = structlog.get_logger(__name__)


class Bitrix24Mota:
    def __init__(self, client_settings):
        self.bitrix_url = client_settings['bitrix_api_url']
        self.bitrix_field_properties = client_settings['bitrix_field_properties']

    def get_bitrix_connection(self):
        return Bitrix24(self.bitrix_url)

    def clean_stock_configuration_schema(self, product_details):
        try:
            bx24 = self.get_bitrix_connection()
            product_details = urllib.parse.parse_qs(product_details.decode("UTF-8"))
            product_id = int(product_details["data[FIELDS][ID]"][0])
            response = bx24.callMethod('crm.product.get', id=product_id)

            struct_logger.info(event="stock_configuration_bitrix24",
                               stock_configuration_details=response,
                               )
            goods_id = response["ID"]
            goods_name = response["NAME"]
            currency = clean_currency_product(response["CURRENCY_ID"])
            unit_price = response["PRICE"]
            ura_commodity_category = response[self.bitrix_field_properties["efris_commodity_category"]]["value"]
            measure_unit = response[self.bitrix_field_properties["efris_measure_unit"]]["value"]
            description = response["DESCRIPTION"]

            stock_configuration = {
                "goods_name": goods_name,
                "goods_code": goods_id,
                "unit_price": unit_price,
                "measure_unit": measure_unit,
                "currency": currency,
                "commodity_tax_category": ura_commodity_category,
                "goods_description": description
            }

            stock_configuration_schema = IncomingStockConfigurationSchema(**stock_configuration)

            return stock_configuration_schema
        except Exception as ex:
            return str(ex)

    def clean_stock_in_schema(self, product_details, stock_in_type='104', operation_type='101', adjust_type=''):
        bx24 = self.get_bitrix_connection()
        product_details = urllib.parse.parse_qs(product_details.decode("UTF-8"))
        product_id = int(product_details["data[FIELDS][ID]"][0])
        response = bx24.callMethod('crm.product.get', id=product_id)

        goods_id = response["ID"]
        goods_name = response["NAME"]
        quantity = response[self.bitrix_field_properties["efris_quantity"]]["value"]

        purchase_price = response[self.bitrix_field_properties["efris_purchase_price"]]["value"]

        # purchase_price = purchase_price.split("|")[0]
        supplier = response[self.bitrix_field_properties["efris_supplier"]]["value"]

        try:

            supplier_tin = response[self.bitrix_field_properties["efris_supplier_tin"]]["value"]
        except:
            supplier_tin = ""
        struct_logger.info(event="stock_adjustment_bitrix24",
                           stock_in_details=response,
                           field_details=self.bitrix_field_properties
                           )
        goods_name = response["NAME"]

        stock_adjustment = {
            "goods_code": goods_id,
            "supplier": supplier,
            "supplier_tin": supplier_tin,
            "stock_in_type": stock_in_type,
            "quantity": quantity,
            "purchase_price": purchase_price,
            "purchase_remarks": goods_name,
            "operation_type": operation_type,
            "adjust_type": adjust_type
        }
        struct_logger.info(event="stock_adjustment_bitrix24",
                           stock_in_schema=stock_adjustment,
                           )

        stock_adjustment_schema = IncomingGoodsStockAdjustmentSchema(**stock_adjustment)

        return stock_adjustment_schema

    def clean_incoming_invoice_schema(self, invoice_details, industry_code='101', invoice_type='1',
                                      invoice_kind='1', payment_mode='102'):
        bx24 = self.get_bitrix_connection()
        data = urllib.parse.parse_qs(invoice_details.decode("UTF-8"))
        dynamic_event = data['event'][0]
        invoice_id = data["data[FIELDS][ID]"][0]

        struct_logger.info(event="bitrix_incoming_invoice",
                           bitrix_data=data,
                           invoice_id=invoice_id,
                           dynamic_event=dynamic_event
                           )

        try:
            # invoice_id = 541
            bitrix_response = bx24.callMethod('crm.item.get', id=invoice_id)

            struct_logger.info(event="bitrix_incoming_invoice",
                               bitrix_data=data,
                               bitrix_invoice_data=bitrix_response
                               )

            if dynamic_event == 'ONCRMDYNAMICITEMDELETE':
                pass
            elif dynamic_event == 'ONCRMDYNAMICITEMADD':

                struct_logger.info(event="bitrix_incoming_invoice",
                                   message='ONCRMDYNAMICITEMADD',
                                   bitrix_invoice_data=bitrix_response
                                   )

                invoice_id = bitrix_response["ID"]
                cashier = bitrix_response["RESPONSIBLE_NAME"]
                currency = clean_currency(bitrix_response["CURRENCY"])
                products = bitrix_response["PRODUCT_ROWS"]
                goods_details = []
                buyer_details = bitrix_response["INVOICE_PROPERTIES"]
                buyer_type = clean_buyer_type(self.bitrix_field_properties["efris_buyer_type"])
                buyer_tin = clean_buyer_type(self.bitrix_field_properties["efris_buyer_tin"])

                try:
                    buyer_name = buyer_details["COMPANY"]
                except:
                    buyer_name = buyer_details["FIO"]

                if buyer_type in '0' and buyer_tin == "":
                    return {"error_code": "invalid data", "msg": "tax pin required"}
                buyer_details = BuyerDetailsSchema(tax_pin=buyer_tin,
                                                   nin="",
                                                   passport_number="",
                                                   legal_name=buyer_name,
                                                   business_name=buyer_name,
                                                   address="",
                                                   email="",
                                                   mobile="",
                                                   buyer_type=buyer_type,
                                                   buyer_citizenship="",
                                                   buyer_sector="",
                                                   buyer_reference=""
                                                   )
                for product in products:
                    good = InvoiceGoodSchema(good_code=product["ID"],
                                             quantity=product["QUANTITY"],
                                             sale_price=product["PRICE"])

                    goods_details.append(good)

                incoming_invoice_schema = TaxInvoiceIncomingSchema(
                    invoice_details=InvoiceDetailsSchema(
                        invoice_code=invoice_id,
                        cashier=cashier,
                        payment_mode=payment_mode,
                        currency=currency,
                        invoice_type=invoice_type,
                        invoice_kind=invoice_kind,
                        goods_description=cashier,
                        industry_code=industry_code
                    ),
                    instance_invoice_id=invoice_id,
                    buyer_details=buyer_details,
                    goods_details=goods_details
                )

                struct_logger.info(event="bitrix_incoming_invoice",
                                   invoice_schema=incoming_invoice_schema,

                                   )

                return incoming_invoice_schema
        except Exception as ex:
            struct_logger.error(event="bitrix_incoming_invoice",
                                error=str(ex),

                                )

    def clean_incoming_credit_note_schema(self, invoice_details):
        bx24 = self.get_bitrix_connection()
        data = urllib.parse.parse_qs(invoice_details.decode("UTF-8"))
        struct_logger.info(event="bitrix_incoming_invoice",
                           bitrix_data=data,
                           )
        invoice_id = data["data[FIELDS][ID]"][0]

        bitrix_response = bx24.callMethod('crm.invoice.get', id=invoice_id)

        struct_logger.info(event="bitrix_incoming_invoice",
                           bitrix_data=data,
                           bitrix_invoice_data=bitrix_response
                           )
        invoice_id = bitrix_response["ID"]
        cashier = bitrix_response["RESPONSIBLE_NAME"]
        currency = clean_currency(bitrix_response["CURRENCY"])
        products = bitrix_response["PRODUCT_ROWS"]
        goods_details = []
        buyer_details = bitrix_response["INVOICE_PROPERTIES"]
        buyer_type = clean_buyer_type(bitrix_response["UF_CRM_1625154158"])
        buyer_tin = bitrix_response["UF_CRM_1625492650"] if bitrix_response["UF_CRM_1625492650"] else ""
        industry_code = "101"
        try:
            buyer_name = buyer_details["COMPANY"]
        except:
            buyer_name = buyer_details["FIO"]

        if buyer_type in '0' and buyer_tin == "":
            return {"error_code": "invalid data", "msg": "tax pin required"}
        buyer_details = BuyerDetailsSchema(tax_pin=buyer_tin,
                                           nin="",
                                           passport_number="",
                                           legal_name=buyer_name,
                                           business_name=buyer_name,
                                           address="",
                                           email="",
                                           mobile="",
                                           buyer_type=buyer_type,
                                           buyer_citizenship="",
                                           buyer_sector="",
                                           buyer_reference=""
                                           )
        for product in products:
            good = InvoiceGoodSchema(good_code=product["PRODUCT_ID"],
                                     quantity=product["QUANTITY"],
                                     sale_price=product["PRICE"])

            goods_details.append(good)

        incoming_invoice_schema = TaxInvoiceIncomingSchema(
            invoice_details=InvoiceDetailsSchema(
                invoice_code=invoice_id,
                cashier=cashier,
                payment_mode="102",
                currency=currency,
                invoice_type="1",
                invoice_kind="1",
                goods_description=cashier,
                industry_code=industry_code
            ),
            instance_invoice_id=invoice_id,
            buyer_details=buyer_details,
            goods_details=goods_details
        )

        return incoming_invoice_schema
