from base64 import b64encode

import structlog

from app.api.handlers.UG.api import EFRIS

struct_logger = structlog.get_logger(__name__)

from app.api.handlers.information_handler import InformationHandler


class TaxInformationHandler(InformationHandler):

    def __init__(self, settings):
        self.client = EFRIS(settings)

    async def get_stock_quantity(self, goods_code):
        return "hello"

    async def get_dictionary(self):
        await self.client.get_key_signature()

        efris_dictionary = await self.client.update_efris_dictionary()

        return efris_dictionary

    def convert_response(self, response):
        return True, response
        # return True, str(type(response['data']['content']))
