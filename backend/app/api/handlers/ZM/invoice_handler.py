import datetime
import time
import structlog
from fastapi import HTTPException
from app.api.handlers.ZM.api import ZRA
from app.api.handlers.invoice_handler import InvoiceHandler
from app.api.dependencies.database import get_database
from app.models.invoice_dal import get_invoice_blank_number, get_invoice_number_code, create_invoice_number, \
    update_invoice_number, get_invoice
from app.db.schemas.invoice import TaxInvoiceIncomingSchema, InvoiceNumberSchema


struct_logger = structlog.get_logger(__name__)


class TaxInvoiceHandler(InvoiceHandler):
    def __init__(self, settings):

        self.invoice_number = None
        self.zra_related_invoice = None
        self.json_data = {}
        self.api_response = {}
        self.zra_invoice_number = ""
        self.zra_invoice_code = ""
        self.zra_related_invoice_number = None
        self.invoice_status = "01"
        self.items_info = []
        self.items_tax_summary = []
        self.local_purchase_order = ""
        self.conversion_rate = 1
        self.sales_type = 1
        self.remarks = ""
        self.zra_related_invoice_code = None
        self.fiscal_code = None
        self.invoice_tax_amount_total = 0.00
        self.invoice_amount_total = 0.00
        self.tax_invoice = None
        self.buyer_details = None
        self.taxable_items = None
        self.invoice_data = None
        self.client = ZRA(settings)
        self.settings = settings
        self.utc_time, self.invoice_time = self.get_invoice_time()
        self.session = get_database()

    async def blank_invoice_number_request(self):
        try:
            blank_invoice_number = get_invoice_blank_number( self.session, self.client.tax_pin)

            if blank_invoice_number:

                return blank_invoice_number

            else:

                response = await self.client.invoice_application_request()
                success, response = self.client.process_zra_response(response)
                struct_logger.info(event="blank_invoice_number_request", api="zra", data=response)
                invoices = response["invoice"]

                for invoice in invoices:

                    if get_invoice_number_code( self.session, self.client.tax_pin, invoice["code"], invoice["number-begin"]):
                        struct_logger.warn("invoice_application_request",
                                           invoice_code=invoice["code"],
                                           invoice_number_end=invoice["number-end"],
                                           msg="Failed to save invoice numbers",
                                           description="ZM invoice already exists in database",
                                           )

                    else:

                        for invoice_number in range(int(invoice["number-begin"]), int(invoice["number-end"]) + 1):
                            new_invoice_number_details = {
                                "invoice_code": invoice["code"],
                                "invoice_number": invoice_number,
                                "number_begin": invoice["number-begin"],
                                "number_end": invoice["number-end"],
                                "tax_id": self.client.tax_pin

                            }

                            invoice_number_base = InvoiceNumberSchema(**new_invoice_number_details)

                            new_invoice_number = create_invoice_number( self.session, invoice_number_base)

                            struct_logger.info(event='invoice_application_request', msg="Saving ZRA Invoices",
                                               response=response, db_number=new_invoice_number)

                return get_invoice_blank_number( self.session, self.client.tax_pin)

        except Exception as ex:
            struct_logger.info(event='invoice_application_request', msg="Error Saving ZRA Invoices", error=str(ex))
            return None

    async def convert_request(self,db, tax_invoice: TaxInvoiceIncomingSchema):
        self.taxable_items = tax_invoice.goods_details
        self.invoice_data = tax_invoice.invoice_details
        self.buyer_details = tax_invoice.buyer_details
        self.tax_invoice = tax_invoice
        self.zra_related_invoice_code = self.invoice_data.original_instance_invoice_id
        self.invoice_number = await self.blank_invoice_number_request()
        items_info = []
        tax_info = []
        item_no = 0
        count = 1
        invoice_tax_amount_total = 0.00
        zra_related_invoice_code = ""
        zra_related_invoice_number = ""
        fiscal_time, invoice_time = self.utc_time, self.invoice_time
        fiscal_time = str(fiscal_time).zfill(8)
        isc1 = False
        isc2 = False
        isc3 = False
        isexempt = False
        zero_rated_tax_value = 0.00
        zero_tax_rate = 0.00
        non_zero_tax_rate = 0.16
        category_initial = ''
        category_name = ''
        tax_rate = 0.00
        item_type_tax_amount = 0.00
        taxable_amount = 0.00
        total_item_amount = 0.00
        item_name = ""
        fiscal_code = ""

        if self.buyer_details.tax_pin:
            self.validate_tax_pin()

        if self.invoice_number:
            self.zra_invoice_number = self.invoice_number.invoice_number
            self.zra_invoice_code = self.invoice_number.invoice_code
        else:
            raise HTTPException(status_code=404, detail="Unable to retrieve invoices in ZRA API")

        zra_invoice_number = str(self.zra_invoice_number).zfill(8)
        zra_invoice_code = self.zra_invoice_code

        if self.zra_related_invoice_code:

            related_invoice = get_invoice( self.session, self.zra_related_invoice_code, "ZM", self.client.tax_pin)

            if related_invoice:
                related_invoice_request_data = related_invoice.request_data
            else:
                raise HTTPException(status_code=404, detail="Unable to retrieve old invoice with invoice_id:{}".format(
                    self.zra_related_invoice_code))

            struct_logger.info(event="convert_request",
                               api="zra",
                               message="retrieving credit note",
                               related_invoice=related_invoice.instance_invoice_id)

            zra_related_invoice_code = related_invoice_request_data['declaration-info']['invoice-code']
            zra_related_invoice_number = related_invoice_request_data['declaration-info']['invoice-number']
            total_invoice_amount = '%.2f' % self.invoice_amount_total

            for item_tax in self.taxable_items:
                try:
                    category_initial = item_tax.tax_category
                    tax_details = self.get_tax_category_details(category_initial)
                    category_name = tax_details["tax-name"]
                    tax_rate = float(tax_details["tax-rate"])
                    item_type_tax_amount = item_tax.sale_price * tax_rate
                    item_name = item_tax.good_code
                    taxable_amount = item_tax.sale_price
                    total_item_amount = item_type_tax_amount + taxable_amount

                except Exception as e:
                    struct_logger.error(msg="create ZM json data",
                                        error=e,
                                        description="Failure to retrieve tax information from item types"
                                        )
                if tax_rate == 0.00:
                    item_info = {"no": item_no,
                                 "tax-category-code": category_initial,
                                 "tax-category-name": category_name,
                                 "name": item_name,
                                 "count": count,
                                 "amount": float("-{:.2f}".format(total_item_amount)),
                                 "tax-amount": float("-{:.2f}".format(item_type_tax_amount)),
                                 "unit-price": float("-{:.2f}".format(taxable_amount)),
                                 "tax-rate": tax_rate,
                                 }
                    if category_initial == "D":
                        isexempt = True

                    if category_initial == 'C1':
                        isc1 = True

                    if category_initial == 'C3':
                        isc3 = True

                else:
                    item_info = {"no": item_no,
                                 "tax-category-code": category_initial,
                                 "tax-category-name": category_name,
                                 "name": item_name,
                                 "count": count,
                                 "amount": float("-{:.2f}".format(taxable_amount)),
                                 "tax-amount": float("-{:.2f}".format(item_type_tax_amount)),
                                 "unit-price": float("-{:.2f}".format(total_item_amount)),
                                 "tax-rate": tax_rate,
                                 }
                    non_zero_tax_rate = tax_rate

                items_info.append(item_info)

                item_no += 1
                invoice_tax_amount_total += item_type_tax_amount

            if isc1:
                c1_tax_info = {"tax-code": "C1",
                               "tax-name": "Export",
                               "tax-rate": zero_tax_rate,
                               "tax-value": float("-{:.2f}".format(zero_rated_tax_value))
                               }
                tax_info.append(c1_tax_info)
            if isc2:
                c2_tax_info = {"tax-code": "C2",
                               "tax-name": "Privilege Person",
                               "tax-rate": zero_tax_rate,
                               "tax-value": float("-{:.2f}".format(zero_rated_tax_value))
                               }
                tax_info.append(c2_tax_info)
            if isc3:
                c3_tax_info = {"tax-code": "C3",
                               "tax-name": "Zero Rate",
                               "tax-rate": zero_tax_rate,
                               "tax-value": float("-{:.2f}".format(zero_rated_tax_value))
                               }
                tax_info.append(c3_tax_info)
            if isexempt:
                exempt_tax_info = {"tax-code": "D",
                                   "tax-name": "Exempt",
                                   "tax-rate": zero_tax_rate,
                                   "tax-value": float("-{:.2f}".format(zero_rated_tax_value))
                                   }
                tax_info.append(exempt_tax_info)

            non_zero_tax_info = {"tax-code": "A",
                                 "tax-name": "Standard Rate",
                                 "tax-rate": non_zero_tax_rate,
                                 "tax-value": float("-{:.2f}".format(invoice_tax_amount_total))
                                 }
            tax_info.append(non_zero_tax_info)
            total_invoice_amount = '-%.2f' % (float(total_invoice_amount) + float(invoice_tax_amount_total))
            self.invoice_amount_total = total_invoice_amount

        elif self.buyer_details.is_privileged:

            self.validate_privileged_person()
            total_invoice_amount = '%.2f' % self.invoice_amount_total

            for item_tax in self.taxable_items:
                try:

                    tax_rate = float(0.00)
                    item_type_tax_amount = item_tax.sale_price * tax_rate
                    item_name = item_tax.good_code
                    taxable_amount = item_tax.sale_price
                    total_item_amount = item_type_tax_amount + taxable_amount

                except Exception as e:
                    struct_logger.error(event="convert_request",
                                        api="zra",
                                        msg="create ZM json data",
                                        error=e,
                                        description="Failure to retrieve tax information from item types"
                                        )

                item_info = {"no": item_no,
                             "tax-category-code": "C2",
                             "tax-category-name": "Privilege Person",
                             "name": item_name,
                             "count": count,
                             "amount": total_item_amount,
                             "tax-amount": item_type_tax_amount,
                             "unit-price": taxable_amount,
                             "tax-rate": tax_rate,
                             }

                items_info.append(item_info)
                item_no += 1
                invoice_tax_amount_total += item_type_tax_amount

            c2_tax_info = {"tax-code": "C2",
                           "tax-name": "Privilege Person",
                           "tax-rate": zero_tax_rate,
                           "tax-value": zero_rated_tax_value
                           }
            tax_info.append(c2_tax_info)
            total_invoice_amount = '%.2f' % (float(total_invoice_amount) + float(invoice_tax_amount_total))
            self.invoice_amount_total = total_invoice_amount

        else:
            total_invoice_amount = '%.2f' % self.invoice_amount_total
            for item_tax in self.taxable_items:
                try:
                    category_initial = item_tax.tax_category
                    tax_details = self.get_tax_category_details(category_initial)
                    category_name = tax_details["tax-name"]
                    tax_rate = float(tax_details["tax-rate"])
                    item_type_tax_amount = item_tax.sale_price * tax_rate
                    item_name = item_tax.good_code
                    taxable_amount = item_tax.sale_price
                    total_item_amount = item_type_tax_amount + taxable_amount

                except Exception as e:
                    struct_logger.error(msg="create ZM json data",
                                        error=e,
                                        description="Failure to retrieve tax information from item types"
                                        )
                if tax_rate == 0.00:
                    item_info = {"no": item_no,
                                 "tax-category-code": category_initial,
                                 "tax-category-name": category_name,
                                 "name": item_name,
                                 "count": count,
                                 "amount": total_item_amount,
                                 "tax-amount": item_type_tax_amount,
                                 "unit-price": taxable_amount,
                                 "tax-rate": tax_rate,
                                 }
                    if category_initial == "D":
                        isexempt = True

                    if category_initial == 'C1':
                        isc1 = True

                    if category_initial == 'C3':
                        isc3 = True

                else:
                    item_info = {"no": item_no,
                                 "tax-category-code": category_initial,
                                 "tax-category-name": category_name,
                                 "name": item_name,
                                 "count": count,
                                 "amount": taxable_amount,
                                 "tax-amount": item_type_tax_amount,
                                 "unit-price": total_item_amount,
                                 "tax-rate": tax_rate,
                                 }
                    non_zero_tax_rate = tax_rate

                items_info.append(item_info)

                item_no += 1
                invoice_tax_amount_total += item_type_tax_amount

            if isc1:
                c1_tax_info = {"tax-code": "C1",
                               "tax-name": "Export",
                               "tax-rate": zero_tax_rate,
                               "tax-value": zero_rated_tax_value
                               }
                tax_info.append(c1_tax_info)
            if isc2:
                c2_tax_info = {"tax-code": "C2",
                               "tax-name": "Privilege Person",
                               "tax-rate": zero_tax_rate,
                               "tax-value": zero_rated_tax_value
                               }
                tax_info.append(c2_tax_info)
            if isc3:
                c3_tax_info = {"tax-code": "C3",
                               "tax-name": "Zero Rate",
                               "tax-rate": zero_tax_rate,
                               "tax-value": zero_rated_tax_value
                               }
                tax_info.append(c3_tax_info)
            if isexempt:
                exempt_tax_info = {"tax-code": "D",
                                   "tax-name": "Exempt",
                                   "tax-rate": zero_tax_rate,
                                   "tax-value": zero_rated_tax_value
                                   }
                tax_info.append(exempt_tax_info)

            non_zero_tax_info = {"tax-code": "A",
                                 "tax-name": "Standard Rate",
                                 "tax-rate": non_zero_tax_rate,
                                 "tax-value": invoice_tax_amount_total
                                 }
            tax_info.append(non_zero_tax_info)
            total_invoice_amount = '%.2f' % (float(total_invoice_amount) + float(invoice_tax_amount_total))
            self.invoice_amount_total = total_invoice_amount

        try:
            fiscal_code = self.fiscal_code_cal(zra_invoice_code, zra_invoice_number, fiscal_time, total_invoice_amount)
        except Exception as ex:
            struct_logger.error(msg="create ZM json data",
                                error=ex,
                                description="Failed to create Fiscal Code. Invalid parameters provided."
                                )

        self.json_data = {
            "declaration-info": {"invoice-code": zra_invoice_code,
                                 "invoice-number": zra_invoice_number,
                                 "buyer-tpin": self.buyer_details.tax_pin,
                                 "buyer-vat-acc-name": self.buyer_details.legal_name,
                                 "buyer-name": self.buyer_details.legal_name,
                                 "buyer-address": "",
                                 "buyer-tel": "",
                                 "tax-amount": invoice_tax_amount_total,
                                 "total-amount": total_invoice_amount,
                                 "total-discount": 0,
                                 "invoice-status": self.invoice_status,
                                 "invoice-issuer": self.invoice_data.cashier,
                                 "invoicing-time": invoice_time,
                                 "old-invoice-code": zra_related_invoice_code,
                                 "old-invoice-number": zra_related_invoice_number,
                                 "fiscal-code": fiscal_code.decode('UTF-8'),
                                 "memo": self.remarks,
                                 "sale-type": self.sales_type,
                                 "currency-type": "ZMW",
                                 "conversion-rate": self.conversion_rate,
                                 "local-purchase-order": self.buyer_details.local_purchase_order,
                                 "voucher-PIN": "",
                                 "items-info": items_info,
                                 "tax-info": tax_info
                                 },
            "POS-SN": self.invoice_data.cashier,
            "id": self.client.terminal_id
        }
        struct_logger.info(event="convert_request", api="zra", data=self.json_data)

        update_invoice_number( self.session, tax_invoice.instance_invoice_id,
                              self.client.tax_pin,
                              self.zra_invoice_code,
                              self.zra_invoice_number
                              )

        return self.json_data

    async def _send_invoice(self, request_data):
        zra = ZRA(self.settings)
        return await zra.send_invoice(request_data)

    def convert_response(self, response):
        success, response = self.client.process_zra_response(response)

        struct_logger.info(event="convert_response", api="zra", data=response)

        if response['code'] == "200":

            return True, response

        else:
            return False, response

    def validate_tax_pin(self):
        if len(self.buyer_details.tax_pin) != 10:
            raise HTTPException(status_code=404, detail="Buyer tax_pin should only 10 digits")

        elif not self.buyer_details.tax_pin.isdigit():
            raise HTTPException(status_code=404, detail="Buyer tax_pin should only be digits")

    def validate_privileged_person(self):

        if not self.buyer_details.local_purchase_order:
            # Validate purchase order
            struct_logger.error(event="convert_request",
                                api="zra",
                                msg="create ZM json data",
                                error='Privileged Person Mode requires an LPO',
                                description="Insufficient information provided to create privileged Person Invoice"
                                )
            raise HTTPException(status_code=404, detail="Local Purchase Order is required for privileged persons")

        elif not self.buyer_details.tax_pin:
            # Validate tax_pin
            struct_logger.error(event="convert_request",
                                api="zra",
                                msg="create ZM json data",
                                error='Privileged Person Mode requires an LPO',
                                description="Insufficient information provided to create privileged Person Invoice"
                                )
            raise HTTPException(status_code=404, detail="Buyer tax_pin is required for privileged persons")

        elif len(self.buyer_details.local_purchase_order) > 10:
            raise HTTPException(status_code=404, detail="Local Purchase Order should be less than 10 digits")

        self.validate_tax_pin()

    def validate_buyer_details(self):
        pass

    def get_tax_category_details(self, category_initial):
        global tax_info
        if self.invoice_data.is_export:

            tax_info = {"tax-code": "C1",
                        "tax-name": "Export",
                        "tax-rate": "0.00",
                        "tax-value": "0.00"
                        }

        elif self.buyer_details.is_privileged:
            tax_info = {"tax-code": "C2",
                        "tax-name": "Privilege Person",
                        "tax-rate": "0.00",
                        "tax-value": "0.00"
                        }
        elif category_initial == "C3":

            tax_info = {"tax-code": "C3",
                        "tax-name": "Zero Rate",
                        "tax-rate": "0.00",
                        "tax-value": "0.00"
                        }

        elif category_initial == "D":

            tax_info = {"tax-code": "D",
                        "tax-name": "Exempt",
                        "tax-rate": "0.00",
                        "tax-value": "0.00"
                        }

        elif category_initial == "A":

            tax_info = {"tax-code": "A",
                        "tax-name": "Standard Rate",
                        "tax-rate": "0.18",
                        "tax-value": "0.18"
                        }

        return tax_info

    def fiscal_code_cal(self, invoice_code, invoice_number, utc_time, total_invoice_amount):
        """
        This method is used to retrieve the fiscal code from the DLL shared by ZRA
        """
        tax_pin = self.client.tax_pin.zfill(18)
        invoice_code = str(invoice_code).zfill(12)
        invoice_num = str(invoice_number).zfill(8)
        utc_time = str(utc_time).zfill(14)
        terminal_id = self.client.terminal_id.zfill(12)
        amount = total_invoice_amount.rjust(20, '0')
        fiscal_code = self.client.fiscal_code_obj.get_fiscal_code(tax_pin,
                                                                  invoice_code,
                                                                  invoice_num,
                                                                  utc_time,
                                                                  terminal_id,
                                                                  amount,
                                                                  self.client.zra_private_key)

        return fiscal_code

    @staticmethod
    def get_invoice_time():
        invoice_time = int(time.time())
        fiscal_time = invoice_time + 7200
        fiscal_unix_timestamp = str(
            datetime.datetime.utcfromtimestamp(fiscal_time).strftime('%Y-%m-%d %H:%M:%S')).replace(':', '').replace('-',
                                                                                                                    '').replace(
            ' ', '').strip()
        return int(fiscal_unix_timestamp), invoice_time
