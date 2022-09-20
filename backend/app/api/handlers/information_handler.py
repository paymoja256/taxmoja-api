import structlog

struct_logger = structlog.get_logger(__name__)


class InformationHandler:
    """
    Base class for integrations with tax services
    that involve information retrieval request
    """

    def __init__(self, settings):
        """
        Usually, some settings will be needed to initialize a client
        """

    async def get_information_request(self,
                                      information_request
                                      ):

        try:

            api_response = await getattr(self, information_request)()

            success, response_data = self.convert_response(api_response)

            struct_logger.info(event='Information handler',
                               message="sending information request",
                               function=information_request,
                               status=success,
                               response=response_data
                               )

            return response_data

        except Exception as ex:
            struct_logger.info(event='benin_request_data',
                               message="sending benin api request",
                               function=information_request,
                               status="failed",
                               error=str(ex)
                               )
            return str(ex)

    def convert_response(self, api_response):
        raise NotImplementedError
