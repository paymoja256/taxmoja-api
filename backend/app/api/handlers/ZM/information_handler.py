import structlog
from app.api.handlers.ZM.api import ZRA
from app.api.handlers.information_handler import InformationHandler


struct_logger = structlog.get_logger(__name__)


class TaxInformationHandler(InformationHandler):

    def __init__(self, settings):

        super().__init__(settings)
        self.client = ZRA(settings)

    async def private_key_application(self):
        return await self.client.private_key_application()

    async def tax_information_request(self):
        return await self.client.tax_information_request()

    async def initialisation_success(self):
        return await self.client.initialisation_success_request()

    async def heart_beat_request(self):
        return await self.client.heart_beat_request()

    async def invoice_number_application(self):
        return await self.client.invoice_application_request()

    def convert_response(self, response):
        success, response = self.client.process_zra_response(response)

        struct_logger.info(event="convert_response", api="zra", data=response)

        # return response

        if response['code'] == "200":

            return True, response

        else:
            return False, response
