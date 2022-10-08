from app.api.handlers.UG.api import EFRIS
from app.api.handlers.stock_handler import StockHandler
from app.db.schemas.stock import IncomingGoodsStockAdjustmentSchema, IncomingStockConfigurationSchema


class TaxStockHandler(StockHandler):

    def __init__(self, settings):
        self.client = EFRIS(settings)

    def convert_stock_upload_request(self, goods_detail: IncomingStockConfigurationSchema):
        data = [
            {
                "operationType": "101",
                "goodsName": goods_detail.goods_name,
                "goodsCode": goods_detail.goods_code,
                "measureUnit": goods_detail.measure_unit,
                "unitPrice": goods_detail.unit_price,
                "currency": goods_detail.currency,
                "commodityCategoryId": goods_detail.commodity_tax_category,
                "haveExciseTax": "102",
                "description": goods_detail.goods_description,
                "stockPrewarning": "0",
                "pieceMeasureUnit": "",
                "havePieceUnit": "102",
                "pieceUnitPrice": "",
                "packageScaledValue": "",
                "pieceScaledValue": "",
                "exciseDutyCode": "",
                "haveOtherUnit": "102",
                "goodsOtherUnits": [

                ]
            }
        ]
        return data
        # return await self.client.goods_upload(goods_detail)

    async def send_goods_stock_adjustment(self, db, goods_detail: IncomingGoodsStockAdjustmentSchema):
        await self.client.get_key_signature()
        response = await self.client.goods_stock_in(db,goods_detail)

        return response

    async def stock_quantity(self, goods_code):
        return await self.client.stock_quantity_by_goods_id(goods_code)

    async def _upload_stock(self, request_data):
        await self.client.get_key_signature()
        return await self.client.goods_upload(request_data)

    def convert_response(self, response):
        
        is_success = False
        
        if response==[]:
            is_success = True
            response = "Success"
            
        else:
            if hasattr(response, 'get'):
                response = response.get('returnStateInfo', None)
                
        return is_success, response
    

            