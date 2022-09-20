import structlog

from app.api.dependencies.http import HttpxRequest

struct_logger = structlog.get_logger(__name__)


class EfrisBase:

    def __init__(self, settings):
        self.url = settings['efris_url_online']

    def api_request(self, method, data=None):
        headers = {}
        req = HttpxRequest(self.url)
        return req.httpx_request(method, data, headers=headers)
