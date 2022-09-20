import datetime
import json
import pytz
import structlog

from fastapi import HTTPException
from app.api.handlers.UG.api import EFRIS
from app.api.handlers.invoice_handler import InvoiceHandler
from app.db.schemas.invoice import TaxInvoiceIncomingSchema, CreditNoteCancelSchema

struct_logger = structlog.get_logger(__name__)


class TaxInvoiceHandler(InvoiceHandler):

    def __init__(self, settings):

        self.invoice_code = None
        self.tax_invoice = {}
        self.uga_tax_pin = settings['tax_pin']
        self.taxable_items = {}
        self.invoice_data = []
        self.buyer_details = {}
        self.uga_email_address = settings['client_email']
        self.uga_legal_name = settings['client_name']
        self.uga_business_name = settings['client_name']
        self.uga_address = settings['client_address']
        self.uga_mobile_phone = settings['client_mobile']
        self.uga_place_business = settings['client_address']
        self.device_no = settings['efris_device_no']
        self.total_taxable_amount = 0
        self.total_gross_amount = 0
        self.total_net_amount = 0
        self.item_count = 0
        self.item_no = 1
        self.goods_details = []
        self.tax_details = []
        self.payway = []
        self.request_time = get_invoice_time()
        self.request_data = {}
        self.response_data = {}
        self.invoice_id = ''
        self.invoice_number = ''
        self.anti_fake_code = ''
        self.qr_code = ''
        self.upload_code = ''
        self.upload_desc = ''
        self.invoice_type = '1'
        self.tax_symbol = '03'
        self.tax_rate = "-"
        self.tax_value = "0.00"
        self.tax_category = "exempt"
        self.json_data = {}
        self.transaction_summary = {}
        self.reason = ''
        self.reason_code = ''
        self.original_invoice_id = ''
        self.api_response = None
        self.client = EFRIS(settings)
        self.credit_tax_details = []
        self.credit_goods_details = []
        self.credit_payway_details = []
        self.original_invoice_code = ''

    async def convert_request(self, db, tax_invoice: TaxInvoiceIncomingSchema):
        await self.client.get_key_signature()
        self.taxable_items = tax_invoice.goods_details
        self.invoice_data = tax_invoice.invoice_details
        self.buyer_details = tax_invoice.buyer_details
        self.original_invoice_id = tax_invoice.invoice_details.original_instance_invoice_id
        self.tax_invoice = tax_invoice
        self.validate_buyer_details()

        if self.invoice_data.original_instance_invoice_id:
            return await self.create_credit_invoice(db)

        else:

            return await self.create_normal_invoice(db)

    async def create_normal_invoice(self, db):
        try:

            for taxable_item in self.taxable_items:
                goods_code = taxable_item.good_code
                quantity = taxable_item.quantity
                sale_price = taxable_item.sale_price
                tax_detail = await self.client.goods_inquiry(db, goods_code)
                struct_logger.info(event="post_normal_invoice", tax_detail=tax_detail)
                if tax_detail:
                    unit_price = sale_price
                    total = float(unit_price) * float(quantity)
                    is_zero_rate = tax_detail["isZeroRate"]
                    is_exempt = tax_detail["isExempt"]
                    measure_unit = tax_detail["measureUnit"]
                    self.set_tax_categories(is_exempt, is_zero_rate)
                    net_amount = float(total) / (1 + float(self.tax_value))
                    self.total_net_amount = self.total_net_amount + net_amount
                    tax_amount = float(net_amount) * float(self.tax_value)
                    self.total_taxable_amount = self.total_taxable_amount + tax_amount
                    self.total_gross_amount = self.total_gross_amount + float(total)
                    goods_detail = {
                        "item": tax_detail["goodsName"],
                        "itemCode": tax_detail["goodsCode"],
                        "qty": quantity,
                        "unitOfMeasure": measure_unit,
                        "unitPrice": sale_price,
                        "total": "{:.2f}".format(total),
                        "taxRate": self.tax_rate,
                        "tax": "{:.2f}".format(tax_amount),
                        "discountTotal": "",
                        "discountTaxRate": "",
                        "orderNumber": str(self.item_count),
                        "discountFlag": "2",
                        "deemedFlag": "2",
                        "exciseFlag": "2",
                        "categoryId": "",
                        "categoryName": "",
                        "goodsCategoryId": tax_detail["commodityCategoryCode"],
                        "goodsCategoryName": tax_detail["commodityCategoryName"],
                        "exciseRate": "",
                        "exciseRule": "",
                        "exciseTax": "",
                        "pack": "",
                        "stick": "",
                        "exciseUnit": "",
                        "exciseCurrency": "",
                        "exciseRateName": ""
                    }
                    tax_detail = {
                        "taxCategoryCode": self.tax_symbol,
                        "netAmount": "{:.2f}".format(net_amount),
                        "taxRate": self.tax_rate,
                        "taxAmount": "{:.2f}".format(tax_amount),
                        "grossAmount": "{:.2f}".format(total),
                        "exciseUnit": "",
                        "exciseCurrency": "",
                        "taxRateName": self.tax_category
                    }
                    item_payway = {
                        "paymentMode": "101",
                        "paymentAmount": "{:.2f}".format(total),
                        "orderNumber": self.item_count
                    }
                    self.item_count = self.item_count + 1
                    self.item_no = self.item_no + 1
                    self.goods_details.append(goods_detail)
                    self.tax_details.append(tax_detail)
                    self.payway.append(item_payway)
                else:
                    struct_logger.error(event='convert_request', api="efris", item=goods_code,
                                        message='item tax details not successfully retrieved from UG')
                    raise HTTPException(status_code=404, detail="Unable to create request data in Efris api for "
                                                                "invoice {}".format(
                        self.tax_invoice.instance_invoice_id))

            self.transaction_summary = {
                "netAmount": "{:.2f}".format(self.total_net_amount),
                "taxAmount": "{:.2f}".format(self.total_taxable_amount),
                "grossAmount": "{:.2f}".format(self.total_gross_amount),
                "itemCount": str(self.item_count),
                "modeCode": "1",
                "remarks": str(self.invoice_data.invoice_code),
                "qrCode": ""
            }

            request_data = self.create_normal_invoice_json_data()

            return request_data

        except Exception as ex:
            struct_logger.error(event='post_normal_invoice',
                                msg='failed to create UG invoice..',
                                error=str(ex))
            raise HTTPException(status_code=404,
                                detail="Unable to create request data in Efris api for invoice {}".format(
                                    self.tax_invoice.instance_invoice_id))

    async def create_credit_invoice(self, db):

        try:
            self.reason_code = self.invoice_data.return_reason_code
            self.reason = self.invoice_data.return_reason
            self.invoice_code = self.invoice_data.invoice_code
            self.invoice_type = '2'
            self.original_invoice_code = self.invoice_data.original_instance_invoice_id
            # self.db_invoice = get_invoice_by_code(db, self.original_instance_invoice_id)
            invoice_details = await self.client.all_invoice_query(self.original_invoice_code)
            invoice_no = invoice_details['invoiceNo']
            self.invoice_data = await self.client.get_invoice_details(invoice_no)
            struct_logger.info(event="post_credit_note",
                               invoice_data=self.invoice_data,
                               message="Retrieved from api: {}".format(self.invoice_code))

            self.seller_details = self.invoice_data['sellerDetails']
            self.buyer_details = self.invoice_data['buyerDetails']
            self.invoice_tax_details = self.invoice_data['taxDetails']
            self.invoice_good_details = self.invoice_data['goodsDetails']
            self.invoice_payway_data = self.invoice_data['payWay']
            self.invoice_summary_data = self.invoice_data['summary']
            self.invoice_basic_data = self.invoice_data['basicInformation']
            self.efris_related_invoice_number = self.invoice_basic_data['invoiceNo']
            self.efris_related_invoice_id = self.invoice_basic_data['invoiceId']
            self.currency = self.invoice_basic_data['currency']
            self.buyer_type = self.invoice_data['buyerDetails']['buyerType']

            for taxable_item in self.taxable_items:
                goods_code = taxable_item.good_code
                quantity = taxable_item.quantity
                sale_price = taxable_item.sale_price
                tax_detail = await self.client.goods_inquiry(db, goods_code)
                struct_logger.info(event="post_credit_note", tax_detail=tax_detail)
                if tax_detail:
                    unit_price = sale_price
                    total = float(unit_price) * float(quantity)
                    is_zero_rate = tax_detail["isZeroRate"]
                    is_exempt = tax_detail["isExempt"]
                    measure_unit = tax_detail["measureUnit"]
                    self.set_tax_categories(is_exempt, is_zero_rate)
                    net_amount = float(total) / (1 + float(self.tax_value))
                    self.total_net_amount = self.total_net_amount + net_amount
                    tax_amount = float(net_amount) * float(self.tax_value)
                    self.total_taxable_amount = self.total_taxable_amount + tax_amount
                    self.total_gross_amount = self.total_gross_amount + float(total)
                    goods_detail = {
                        "item": tax_detail["goodsName"],
                        "itemCode": tax_detail["goodsCode"],
                        "qty": "-" + str(quantity),
                        "unitOfMeasure": measure_unit,
                        "unitPrice": sale_price,
                        "total": "-" + "{:.2f}".format(total),
                        "taxRate": self.tax_rate,
                        "tax": "-" + "{:.2f}".format(tax_amount),
                        "discountTotal": "",
                        "discountTaxRate": "",
                        "orderNumber": str(self.item_count),
                        "discountFlag": "2",
                        "deemedFlag": "2",
                        "exciseFlag": "2",
                        "categoryId": "",
                        "categoryName": "",
                        "goodsCategoryId": tax_detail["commodityCategoryCode"],
                        "goodsCategoryName": tax_detail["commodityCategoryName"],
                        "exciseRate": "",
                        "exciseRule": "",
                        "exciseTax": "",
                        "pack": "",
                        "stick": "",
                        "exciseUnit": "",
                        "exciseCurrency": "",
                        "exciseRateName": ""
                    }
                    tax_detail = {
                        "taxCategoryCode": self.tax_symbol,
                        "netAmount": "-" + "{:.2f}".format(net_amount),
                        "taxRate": self.tax_rate,
                        "taxAmount": "-" + "{:.2f}".format(tax_amount),
                        "grossAmount": "-" + "{:.2f}".format(total),
                        "exciseUnit": "",
                        "exciseCurrency": "",
                        "taxRateName": self.tax_category
                    }
                    item_payway = {
                        "paymentMode": "101",
                        "paymentAmount": "-" + "{:.2f}".format(total),
                        "orderNumber": self.item_count
                    }
                    self.item_count = self.item_count + 1
                    self.item_no = self.item_no + 1
                    self.goods_details.append(goods_detail)
                    self.tax_details.append(tax_detail)
                    self.payway.append(item_payway)
                else:
                    struct_logger.error(event='convert_request', api="efris", item=goods_code,
                                        message='item tax details not successfully retrieved from UG')
                    raise HTTPException(status_code=404, detail="Unable to create request data in Efris api for "
                                                                "invoice {}".format(
                        self.tax_invoice.instance_invoice_id))

            self.transaction_summary = {
                "netAmount": "-" + "{:.2f}".format(self.total_net_amount),
                "taxAmount": "-" + "{:.2f}".format(self.total_taxable_amount),
                "grossAmount": "-" + "{:.2f}".format(self.total_gross_amount),
                "itemCount": str(self.item_count),
                "modeCode": "1",
                "remarks": str(self.original_invoice_code),
                "qrCode": ""
            }

            request_data = self.create_credit_note_json_data()

            return request_data


        except Exception as ex:
            struct_logger.error(event='post_credit note',
                                msg='failed to create UG invoice..',
                                error=str(ex))
            raise HTTPException(status_code=404,
                                detail="Unable to create request data in Efris api for credit note{}".format(
                                    self.tax_invoice.instance_invoice_id))

    async def create_credit_invoice_2(self, db):

        try:
            self.reason_code = self.invoice_data.return_reason_code
            self.reason = self.invoice_data.return_reason
            self.invoice_code = self.invoice_data.invoice_code
            self.invoice_type = '2'
            self.original_invoice_code = self.invoice_data.original_instance_invoice_id
            # self.db_invoice = get_invoice_by_code(db, self.original_instance_invoice_id)
            invoice_details = await self.client.all_invoice_query(self.original_invoice_code)
            invoice_no = invoice_details['invoiceNo']
            self.invoice_data = await self.client.get_invoice_details(invoice_no)
            struct_logger.info(event="post_credit_note",
                               invoice_data=self.invoice_data,
                               message="Retrieved from api: {}".format(self.invoice_code))
            # invoice_details = await self.client.all_invoice_query(self.original_invoice_code)
            # invoice_no = invoice_details['invoiceNo']
            # self.invoice_data = await self.client.get_invoice_details(invoice_no)
            # struct_logger.info(event="post_credit_note",
            #                        invoice_data=self.invoice_data,
            #                        message="Retrieved from api: {}".format(self.invoice_code))
            # if self.db_invoice:
            #     self.invoice_data = ast.literal_eval(self.db_invoice.response_data)
            #     struct_logger.info(event="post_credit_note",
            #                        invoice_data=self.invoice_data,
            #                        message="Retrieved from database: {}".format(self.invoice_code))
            # else:

            self.seller_details = self.invoice_data['sellerDetails']
            self.buyer_details = self.invoice_data['buyerDetails']
            self.invoice_tax_details = self.invoice_data['taxDetails']
            self.invoice_good_details = self.invoice_data['goodsDetails']
            self.invoice_payway_data = self.invoice_data['payWay']
            self.invoice_summary_data = self.invoice_data['summary']
            self.invoice_basic_data = self.invoice_data['basicInformation']
            self.efris_related_invoice_number = self.invoice_basic_data['invoiceNo']
            self.efris_related_invoice_id = self.invoice_basic_data['invoiceId']
            self.currency = self.invoice_basic_data['currency']
            self.buyer_type = self.invoice_data['buyerDetails']['buyerType']

            for detail in self.invoice_tax_details:
                credit_tax_detail = {
                    "taxRate": str(detail["taxRate"]),
                    "grossAmount": "-" + str(detail["grossAmount"]),
                    "exciseUnit": "",
                    "taxAmount": "-" + str(detail["taxAmount"]),
                    "taxRateName": str(detail["taxRateName"]),
                    "taxCategoryCode": str(detail["taxCategoryCode"]),
                    "exciseCurrency": "",
                    "netAmount": "-" + str(detail["netAmount"])
                }
                self.credit_tax_details.append(credit_tax_detail)

            for detail in self.invoice_good_details:
                credit_goods_detail = {
                    "taxRate": str(detail["taxRate"]),
                    "exciseRate": "",
                    "orderNumber": str(detail["orderNumber"]),
                    "exciseFlag": "2",
                    "tax": "-" + str(detail["tax"]),
                    "exciseRateName": "",
                    "qty": "-" + str(detail["qty"]),
                    "exciseTax": "",
                    "total": "-" + str(detail["total"]),
                    "discountTaxRate": "",
                    "goodsCategoryId": str(detail["goodsCategoryId"]),
                    "exciseRule": "",
                    "deemedFlag": "2",
                    "discountTotal": "",
                    "categoryId": "",
                    "unitOfMeasure": str(detail["unitOfMeasure"]),
                    "goodsCategoryName": str(detail["goodsCategoryName"]),
                    "itemCode": str(detail["itemCode"]),
                    "stick": "",
                    "exciseCurrency": "",
                    "unitPrice": str(detail["unitPrice"]),
                    "discountFlag": str(detail["discountFlag"]),
                    "exciseUnit": "",
                    "item": str(detail["item"]),
                    "pack": ""
                }
                self.credit_goods_details.append(credit_goods_detail)

            for detail in self.invoice_payway_data:
                credit_payway_detail = {
                    "orderNumber": str(detail["orderNumber"]),
                    "paymentAmount": "-" + str(detail["paymentAmount"]),
                    "paymentMode": str(detail["paymentMode"])
                }
                self.credit_payway_details.append(credit_payway_detail)

            self.credit_summary_detail = {
                "taxAmount": "-" + str(self.invoice_summary_data["taxAmount"]),
                "modeCode": str(self.invoice_summary_data["modeCode"]),
                "grossAmount": "-" + str(self.invoice_summary_data["grossAmount"]),
                "remarks": str(self.invoice_summary_data["remarks"]),
                "qrCode": str(self.invoice_summary_data["qrCode"]),
                "itemCount": str(self.invoice_summary_data["itemCount"]),
                "netAmount": "-" + str(self.invoice_summary_data["netAmount"])
            }

            request_data = self.create_credit_note_json_data()

            return request_data

        except Exception as ex:
            struct_logger.error(event='post_normal_invoice',
                                msg='failed to create UG invoice..',
                                error=str(ex))
            raise HTTPException(status_code=404,
                                detail="Unable to create request data in Efris api for invoice {}".format(
                                    self.tax_invoice.instance_invoice_id))

    def create_normal_invoice_json_data(self):
        self.json_data = {
            "sellerDetails": {
                "tin": self.uga_tax_pin,
                "legalName": self.uga_legal_name,
                "businessName": self.uga_business_name,
                "address": self.uga_address,
                "mobilePhone": self.uga_mobile_phone,
                "linePhone": self.uga_mobile_phone,
                "emailAddress": self.uga_email_address,
                "placeOfBusiness": self.uga_place_business,
                "referenceNo": str(self.invoice_data.invoice_code)
            },
            "basicInformation": {
                "invoiceNo": "",
                "antifakeCode": "",
                "deviceNo": self.device_no,
                "issuedDate": self.request_time,
                "operator": self.invoice_data.cashier,
                "currency": str(self.invoice_data.currency),
                "oriInvoiceId": "",
                "invoiceType": clean_invoice_type(str(self.invoice_data.invoice_type)),
                "invoiceKind": str(self.invoice_data.invoice_kind),
                "dataSource": "103",
                "invoiceIndustryCode": str(self.invoice_data.industry_code),
                "isBatch": ""
            },
            "buyerDetails": {
                "buyerTin": str(self.buyer_details.tax_pin),
                "buyerNinBrn": str(self.buyer_details.nin),
                "buyerPassportNum": str(self.buyer_details.passport_number),
                "buyerLegalName": str(self.buyer_details.legal_name),
                "buyerBusinessName": str(self.buyer_details.business_name),
                "buyerAddress": str(self.buyer_details.address),
                "buyerEmail": str(self.buyer_details.email),
                "buyerMobilePhone": str(self.buyer_details.mobile),
                "buyerLinePhone": str(self.buyer_details.mobile),
                "buyerPlaceOfBusi": str(self.buyer_details.address),
                "buyerType": str(self.buyer_details.buyer_type),
                "buyerCitizenship": str(self.buyer_details.buyer_citizenship),
                "buyerSector": str(self.buyer_details.buyer_sector),
                "buyerReferenceNo": str(self.buyer_details.buyer_reference),
            },
            "goodsDetails": self.goods_details,
            "taxDetails": self.tax_details,
            "summary": self.transaction_summary,
            "payWay": self.payway,
            "extend": {
                "reason": self.reason,
                "reasonCode": self.reason_code
            }

        }

        struct_logger.info('create_normal_json_data', msg='created json data for invoice note',
                           data=self.json_data)

        return self.json_data

    def create_credit_note_json_data(self):
        self.json_data = {"oriInvoiceId": str(self.invoice_basic_data["invoiceId"]),
                          "oriInvoiceNo": str(self.invoice_basic_data["invoiceNo"]),
                          "reasonCode": str(self.reason_code),
                          "reason": str(self.reason),
                          "applicationTime": str(self.request_time),
                          "invoiceApplyCategoryCode": "101",
                          "currency": str(self.invoice_basic_data["currency"]),
                          "contactName": "",
                          "contactMobileNum": "",
                          "contactEmail": "",
                          "source": "103",
                          "remarks": self.invoice_code,
                          "sellersReferenceNo": self.invoice_code,
                          "goodsDetails": self.goods_details,
                          "taxDetails": self.tax_details,
                          "summary": self.transaction_summary,
                          "payWay": self.payway
                          }
        struct_logger.info('create_credit_note_json_data', msg='created json data for credit note',
                           data=self.json_data)

        return self.json_data

    def _send_invoice(self, request_data):
        if self.original_invoice_id:
            return self.client.credit_note_upload(request_data)
        return self.client.send_invoice(request_data)

    async def cancel_invoice(self, tax_invoice: CreditNoteCancelSchema):

        """Get invoice status from database"""
        return self.client.credit_note_cancellation(tax_invoice.original_invoice_id, tax_invoice.credit_note_fdn)

    async def get_invoice_by_instance_id(self, db,
                                         instance_invoice_id,
                                         country_code,
                                         tax_id):

        """Get invoice from database"""

        await self.client.get_key_signature()

        invoice_details = await self.client.all_invoice_query(instance_invoice_id)
        invoice_no = invoice_details['invoiceNo']
        self.invoice_data = await self.client.get_invoice_details(invoice_no)
        struct_logger.info(event="get_invoice_data",
                           invoice_data=self.invoice_data,
                           message="Retrieved from api: {}".format(instance_invoice_id))

        basicInformation = self.invoice_data.get('basicInformation', None)
        if basicInformation:
            anti_fake_code = basicInformation['antifakeCode']
            qr_code = self.invoice_data['summary']['qrCode']

            self.generate_qr_code(qr_code, country_code, tax_id, anti_fake_code)

        return self.invoice_data

    def convert_response(self, response):
        try:
            basicInformation = response.get('basicInformation', None)
            if basicInformation:
                self.invoice_id = basicInformation['invoiceId']
                self.invoice_number = basicInformation['invoiceNo']
                self.anti_fake_code = basicInformation['antifakeCode']
                self.qr_code = response['summary']['qrCode']
                self.upload_code = '200'
                self.upload_desc = 'SUCCESS'
                self.generate_qr_code(self.qr_code, 'UG', self.client.t_pin, self.anti_fake_code)
                struct_logger.info(event='processing UG invoice',
                                   invoice=str(self.invoice_id),
                                   upload_code=self.upload_code,
                                   upload_desc=self.upload_desc,
                                   response=self.response_data
                                   )
                return True, response
            else:
                response_info = response.get('returnStateInfo', None)
                if response_info.get('returnMessage', None):
                    self.upload_code = response_info['returnCode']
                    self.upload_desc = response_info['returnMessage']
                    struct_logger.error(event='processing UG invoice',
                                        response=response,
                                        upload_code=self.upload_code,
                                        upload_desc=self.upload_desc,

                                        msg='uploading UG invoice failed...',
                                        invoice=str(self.invoice_data["invoice_code"])
                                        )

                    return False, response
            # Couldn't get response info
            struct_logger.error(event='processing UG invoice',
                                response=response,
                                msg='uploading UG invoice failed...',
                                invoice=str(self.invoice_data["invoice_code"])
                                )
            return False, response
        except Exception as ex:

            struct_logger.error(event='processing UG invoice',
                                response=response,
                                error=ex,
                                msg='uploading UG invoice failed...',
                                )

            return False, response

    def validate_buyer_details(self):

        if self.buyer_details.buyer_type in ('0', '2', '3'):
            if not clean_tax_pin(self.buyer_details.tax_pin):
                return "Invalid tax pin for non Business to Consumer transaction"

    def set_tax_categories(self, is_exempt, zero_rate):

        if is_exempt == "101":
            self.tax_symbol = '03'
            self.tax_rate = "-"
            self.tax_value = "0.00"
            self.tax_category = "exempt"
        elif zero_rate == "101":
            self.tax_rate = "0.00"
            self.tax_symbol = '02'
            self.tax_category = "Zero Rate"
            self.tax_value = "0.00"
        else:
            self.tax_rate = "0.18"
            self.tax_value = "0.18"
            self.tax_symbol = '01'
            self.tax_category = "Standard Rate"


def get_invoice_time():
    return datetime.datetime.now(tz=pytz.timezone('Africa/Kampala')).strftime("%Y-%m-%d %H:%M:%S.%f")


def clean_tax_pin(tax_pin):
    if not tax_pin.isdigit():
        return False

    elif len(tax_pin) != 10:
        return False

    return True


def clean_invoice_type(invoice_type):
    if invoice_type in ('1', 'normal', 'Normal', 'receipt'):
        return 1

    elif invoice_type in ('2', 'credit'):
        return 2

    else:
        return 1
