import structlog

from app.api.dependencies.http import HttpxRequest

struct_logger = structlog.get_logger(__name__)


class SfeBase:

    def __init__(self, settings):
        self.url = settings['sfe_url']
        # TODO: No! encrypt
        self.token = settings['sfe_token']

        self.ifu = settings['ifu']

    def api_request(self, method, path, data={}):
        headers = {
            'content-type': 'application/json',
            'accept': 'text/plain',
            'Authorization': 'Bearer {}'.format(self.token)
        }

        req = HttpxRequest(self.url + path)

        api_response = req.httpx_request(method, data, headers=headers)

        struct_logger.info(event='benin_api_request',
                           message="sending benin api request",
                           interface=self.url + path,
                           method=method,
                           api_response=api_response
                           )

        return api_response
