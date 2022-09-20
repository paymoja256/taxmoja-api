import structlog

from app.api.dependencies.http import HttpxRequest
from app.api.dependencies.efris_common import clean_currency_product
from app.db.schemas.stock import IncomingStockConfigurationSchema
from app.db.schemas.stock import IncomingGoodsStockAdjustmentSchema
from app.api.dependencies.efris_common import clean_buyer_type, get_tax_rate
from app.db.schemas.invoice import BuyerDetailsSchema, InvoiceGoodSchema, TaxInvoiceIncomingSchema, \
    InvoiceDetailsSchema

struct_logger = structlog.get_logger(__name__)


class Dear:
    def __init__(self, client_settings):
        self.dear_url = client_settings['dear_api_url']
        self.dear_field_properties = client_settings['dear_field_properties']
        self.dear_account_id = client_settings['dear_account_id']
        self.dear_app_key = client_settings['dear_app_key']

    async def send_dear_api_request(self, endpoint: str):
        try:
            request_route = '{}/{}'.format(self.dear_url, endpoint)

            headers = {
                'api-auth-accountid': self.dear_account_id,
                'api-auth-applicationkey': self.dear_app_key
            }
            req = HttpxRequest(request_route)

            return await req.httpx_get_request(headers)
        except Exception as ex:
            return {"message": "DEAR URL is unvailable"}

    async def get_dear_product_details(self, product_id):
        url = "/product?ID={}".format(product_id)
        return await product_id.send_dear_api_request(url)

    async def clean_stock_configuration_schema(self, product_details):

        for sku in product_details:

            try:
                url = "/product?ID={}".format(sku.productID)

                product_data = await self.send_dear_api_request(url)
                product_data = product_data['Products'][0]

                struct_logger.info(event="stock_configuration_dear",
                                   stock_configuration_details=product_data,
                                   )
                goods_id = sku.productID.lower()
                goods_name = sku.productName
                currency = clean_currency_product(product_data[self.dear_field_properties["currency"]])
                unit_price = sku.Price
                ura_commodity_category = product_data[self.dear_field_properties["ura_commodity_category"]]
                measure_unit = product_data[self.dear_field_properties["measure_unit"]]
                description = product_data[self.dear_field_properties["goods_description"]]

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

    async def clean_stock_in_schema(self, product_details, stock_in_type='103', operation_type='101', adjust_type=''):

        for stock in product_details:
            quantity = stock.OnOrder

            purchase_price = self.dear_field_properties['stock_purchase_price']

            supplier = ''

            supplier_tin = ''

            struct_logger.info(event="stock_adjustment_dear",
                               stock_in_details=stock,
                               field_details=self.dear_field_properties
                               )

            stock_adjustment = {
                "goods_code": stock.ID,
                "supplier": supplier,
                "supplier_tin": supplier_tin,
                "stock_in_type": stock_in_type,
                "quantity": quantity,
                "purchase_price": purchase_price,
                "purchase_remarks": stock.Location,
                "operation_type": operation_type,
                "adjust_type": adjust_type
            }
            struct_logger.info(event="stock_adjustment_dear",
                               stock_in_schema=stock_adjustment,
                               )

            stock_adjustment_schema = IncomingGoodsStockAdjustmentSchema(**stock_adjustment)

            return stock_adjustment_schema

    async def clean_stock_in_schema_detail(self, detail, stock_in_type='103', operation_type='101', adjust_type='',
                                           payment_mode='102'):

        task_id = detail['TaskID']
        url = "/stockadjustment?TaskID={}".format(task_id)
        stock_data = await self.send_dear_api_request(url)

        product_details = stock_data['ExistingStockLines']

        for stock in product_details:
            variance = stock['Adjustment'] - stock['QuantityOnHand']

            if variance > 0:
                operation_type = '101'
                adjust_type = ''
                stock_in_type = '103'
            else:
                operation_type = '102'
                adjust_type = '104'
                stock_in_type = ''
            product_data = await self.get_dear_product_details(stock['ProductID'])
            product_data = product_data['Products'][0]

            supplier = ''

            supplier_tin = ''

            struct_logger.info(event="stock_adjustment_dear",
                               stock_in_details=product_data,
                               field_details=self.dear_field_properties

                               )

            stock_adjustment = {
                "goods_code": stock['ProductID'],
                "supplier": supplier,
                "supplier_tin": supplier_tin,
                "stock_in_type": stock_in_type,
                "quantity": abs(variance),
                "purchase_price": product_data['AverageCost'],
                "purchase_remarks": stock_data['StocktakeNumber'],
                "operation_type": operation_type,
                "adjust_type": adjust_type
            }
            struct_logger.info(event="stock_adjustment_dear",
                               stock_in_schema=stock_adjustment,
                               )

            stock_adjustment_schema = IncomingGoodsStockAdjustmentSchema(**stock_adjustment)

            return stock_adjustment_schema

    async def clean_incoming_invoice_schema(self, invoice_details, industry_code='101', invoice_type='1',
                                            invoice_kind='1', payment_mode='102'):
        try:

            task_id = invoice_details['SaleTaskID']
            url = "/sale?ID={}".format(task_id)

            invoice_data = await self.send_dear_api_request(url)

            goods_details = []
            invoices = invoice_data['Invoices']

            struct_logger.info(event="dear_incoming_invoice",
                               dear_data=invoice_details,
                               dear_invoice_data=invoice_data,
                               invoices=invoices
                               )

            url = '/customer?ID={}'.format(invoice_data['CustomerID'])
            customer_data = await self.send_dear_api_request(url)
            struct_logger.info(event="dear_incoming_invoice",
                               dear_data="customer_ invoice_details",
                               dear_invoice_customer_data=customer_data,

                               )
            customer = customer_data['CustomerList'][0]

            if customer['TaxNumber']:
                tax_pin = customer['TaxNumber']
            else:
                tax_pin = customer['AdditionalAttribute2']
            is_export = customer['AdditionalAttribute3']

            if invoice_details['SaleRepEmail']:
                cashier = invoice_details['SaleRepEmail']
            elif customer['SalesRepresentative']:
                cashier = customer['SalesRepresentative']
            else:
                cashier = 'Vital System 01'
            if is_export == 'true':
                industry_code = "102"

            buyer_type = clean_buyer_type(customer['AdditionalAttribute1'])

            if buyer_type in '0' and tax_pin == "":
                return {"error_code": "invalid data", "msg": "tax pin required"}
            buyer_details = BuyerDetailsSchema(tax_pin=tax_pin,
                                               nin="",
                                               passport_number="",
                                               legal_name=invoice_data['Customer'],
                                               business_name=invoice_data['Customer'],
                                               address="",
                                               email=invoice_data['Email'],
                                               mobile=invoice_data['Phone'],
                                               buyer_type=buyer_type,
                                               buyer_citizenship="",
                                               buyer_sector="",
                                               buyer_reference=invoice_data['Customer'][:45]
                                               )

            for invoice in invoices:

                invoice_id = invoice['InvoiceNumber']
                goods = invoice['Lines']
                for product in goods:
                    item_tax = get_tax_rate(product['TaxRule'])
                    good = InvoiceGoodSchema(good_code=product["PRODUCT_ID"],
                                             quantity=product["QUANTITY"],
                                             sale_price=product["PRICE"],
                                             tax_category=item_tax)

                    goods_details.append(good)
                incoming_invoice_schema = TaxInvoiceIncomingSchema(
                    invoice_details=InvoiceDetailsSchema(
                        invoice_code=invoice_id,
                        cashier=cashier,
                        payment_mode=payment_mode,
                        currency=invoice_data['CustomerCurrency'],
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

            return str(ex)

    async def clean_incoming_credit_note_schema(self, invoice_details, industry_code='101', invoice_type='1',
                                                invoice_kind='1', payment_mode='102'):

        try:
            task_id = invoice_details['SaleID']
            url = "/sale/creditnote?SaleID={}".format(task_id)
            goods_details = []

            invoice_data = await self.send_dear_api_request(url)
            invoices = invoice_data['CreditNotes']

            struct_logger.info(event="dear_incoming_credit_note",
                               dear_data=invoice_details,
                               dear_invoice_data=invoice_data,
                               invoices=invoices
                               )

            url = '/customer?ID={}'.format(invoice_data['CustomerID'])
            customer_data = await self.send_dear_api_request(url)
            struct_logger.info(event="dear_incoming_invoice",
                               dear_data="customer_ invoice_details",
                               dear_invoice_customer_data=customer_data,

                               )
            customer = customer_data['CustomerList'][0]

            if customer['TaxNumber']:
                tax_pin = customer['TaxNumber']
            else:
                tax_pin = customer['AdditionalAttribute2']
            is_export = customer['AdditionalAttribute3']

            if invoice_details['SaleRepEmail']:
                cashier = invoice_details['SaleRepEmail']
            elif customer['SalesRepresentative']:
                cashier = customer['SalesRepresentative']
            else:
                cashier = 'Vital System 01'
            if is_export == 'true':
                industry_code = "102"

            buyer_type = clean_buyer_type(customer['AdditionalAttribute1'])

            if buyer_type in '0' and tax_pin == "":
                return {"error_code": "invalid data", "msg": "tax pin required"}
            buyer_details = BuyerDetailsSchema(tax_pin=tax_pin,
                                               nin="",
                                               passport_number="",
                                               legal_name=invoice_data['Customer'],
                                               business_name=invoice_data['Customer'],
                                               address="",
                                               email=invoice_data['Email'],
                                               mobile=invoice_data['Phone'],
                                               buyer_type=buyer_type,
                                               buyer_citizenship="",
                                               buyer_sector="",
                                               buyer_reference=invoice_data['Customer'][:45]
                                               )

            for invoice in invoices:

                invoice_id = invoice['InvoiceNumber']
                goods = invoice['Lines']
                for product in goods:
                    item_tax = get_tax_rate(product['TaxRule'])
                    good = InvoiceGoodSchema(good_code=product["PRODUCT_ID"],
                                             quantity=product["QUANTITY"],
                                             sale_price=product["PRICE"],
                                             tax_category=item_tax)

                    goods_details.append(good)
                incoming_invoice_schema = TaxInvoiceIncomingSchema(
                    invoice_details=InvoiceDetailsSchema(
                        invoice_code=invoice_id,
                        cashier=cashier,
                        payment_mode=payment_mode,
                        currency=invoice_data['CustomerCurrency'],
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

            return str(ex)
