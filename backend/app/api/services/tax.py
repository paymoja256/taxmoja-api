import importlib
from app.db.schemas.core import ClientAuthenticationBase
from app.models.invoice import TaxInvoiceOutgoing
from app.db.schemas.invoice import TaxInvoiceOutgoingSchema
from app.db.schemas.stock import IncomingStockConfigurationSchema, IncomingGoodsStockAdjustmentSchema
from app.models.stock import Stock


class TaxService:

    def __init__(self, interface_details: ClientAuthenticationBase, client_settings):
        self.country_code = interface_details.tax_country_code
        self.tax_id = interface_details.tax_id
        self.client = client_settings
        self.settings = self.client['staging'] if self.client['testing'] else self.client['production']
        self.invoice_module = importlib.import_module("app.api.handlers.%s.invoice_handler" % self.country_code)
        self.stock_module = importlib.import_module("app.api.handlers.%s.stock_handler" % self.country_code)
        self.information_module = importlib.import_module("app.api.handlers.%s.information_handler" % self.country_code)
        self.invoice_handler = getattr(self.invoice_module, "TaxInvoiceHandler")
        self.stock_handler = getattr(self.stock_module, "TaxStockHandler")
        self.information_handler = getattr(self.information_module, "TaxInformationHandler")
        self.invoice_manager = self.invoice_handler(self.settings)
        self.stock_manager = self.stock_handler(self.settings)
        self.information_manager = self.information_handler(self.settings)

    def create_outgoing_invoice(self, db, tax_invoice: TaxInvoiceOutgoingSchema):
        """
        Create an outgoing invoice from an incoming one
        """

        new_invoice = self.invoice_manager.create_outgoing_invoice(db,
                                                                   tax_invoice,
                                                                   self.country_code,
                                                                   self.tax_id)
        return new_invoice

    async def send_invoice(self, db, tax_invoice: TaxInvoiceOutgoing):
        new_invoice = await self.invoice_manager.send_invoice(db, tax_invoice)
        return new_invoice

    async def get_invoice_by_id(self, db, instance_invoice_id):
        invoice = await self.invoice_manager.get_invoice_by_id(db,
                                                               instance_invoice_id,
                                                               self.country_code,
                                                               self.tax_id)
        return invoice

    async def get_invoice_by_instance_id(self, db, instance_invoice_id):
        invoice = await self.invoice_manager.get_invoice_by_instance_id(db,
                                                                        instance_invoice_id,
                                                                        self.country_code,
                                                                        self.tax_id)
        return invoice

    def create_stock_configuration(self, db, stock_configuration: IncomingStockConfigurationSchema):
        new_stock_config = self.stock_manager.create_outgoing_stock_configuration(db,
                                                                                  stock_configuration,
                                                                                  self.country_code,
                                                                                  self.tax_id)
        return new_stock_config

    async def send_stock_configuration(self, db, StockBase: Stock):
        new_stock_configuration = await self.stock_manager.send_stock_configuration(db, StockBase)
        return new_stock_configuration

    async def send_goods_stock_adjustment(self, db, stock_adjustment: IncomingGoodsStockAdjustmentSchema):
        new_stock_adjustment = await self.stock_manager.send_goods_stock_adjustment(db, stock_adjustment)
        return new_stock_adjustment

    async def incoming_information_request(self, information_request: str):
        return await self.information_manager.get_information_request(
            information_request
        )
