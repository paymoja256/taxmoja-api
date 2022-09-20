from app.api.dependencies.http import HttpxRequest


class ZraBase:

    def __init__(self, settings):
        self.url = settings['zra_url']

    def api_request(self, method, data={}):
        headers = {
            'Content-Type': "application/json;Charset=utf-8",
            'Host': "211.90.56.2"
        }

        req = HttpxRequest(self.url)
        return req.httpx_request(method, data, headers=headers)
