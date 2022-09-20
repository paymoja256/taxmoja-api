from pydantic import parse_obj_as
from app.models.invoice import InvoiceStatuses
from app.models.stock_dal import create_stock, save_stock
from app.models.stock import Stock
from app.db.schemas.stock import IncomingStockConfigurationSchema, IncomingGoodsStockAdjustmentSchema

import structlog

struct_logger = structlog.get_logger(__name__)


class StockHandler:
    """
    Base class for integrations with tax services
    that involve uploading stock
    """

    def __init__(self, settings):
        """
        Usually, some settings will be needed to initialize a client
        """
        pass

    def create_outgoing_stock_configuration(self,
                                            db,
                                            stock_configuration: IncomingStockConfigurationSchema,
                                            country_code,
                                            tax_id):
        new_stock_configuration = create_stock(db, stock_configuration, country_code, tax_id)

        struct_logger.info(event='create_outgoing_stock_configuration',
                           message='Saving Stock',
                           tax_id=tax_id,
                           country_code=country_code)

        return new_stock_configuration

    async def send_stock_configuration(self, session, stock: Stock):
        if stock.status == InvoiceStatuses.RECEIVED:
            request_stock = stock.request_stock or parse_obj_as(IncomingStockConfigurationSchema, stock.request_data)
            request_data = self.convert_stock_upload_request(request_stock)
            stock.request_data = request_data
            stock.status = InvoiceStatuses.SENDING

        elif stock.status == InvoiceStatuses.SENT:

            return stock

        else:
            request_data = stock.request_data

        result = await self._upload_stock(request_data)

        success, response_data = self.convert_response(result)

        stock.status = InvoiceStatuses.SENT if success else InvoiceStatuses.ERROR

        stock.response_data = response_data
        save_stock(session, stock)

        struct_logger.info(event='send_stock_configuration',
                           message='Uploading Stock',
                           response=response_data,
                           request=request_data,
                           )

        return stock

    async def send_goods_stock_adjustment(self, db, goods_detail: IncomingGoodsStockAdjustmentSchema):
        raise NotImplementedError

    async def stock_quantity(self, goods_code):
        pass

    def convert_stock_upload_request(self, request_invoice):
        raise NotImplementedError

    async def _upload_stock(self, request_data):
        raise NotImplementedError

    def convert_response(self, result):
        raise NotImplementedError
