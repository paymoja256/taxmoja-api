import pytest
from httpx import AsyncClient
from fastapi import FastAPI

from starlette.status import HTTP_403_FORBIDDEN


class TestAuthenticationHeaders:

    @pytest.mark.asyncio
    async def test_wrong_tax_id(self, app: FastAPI, client: AsyncClient) -> None:
        res = await client.post("/invoice/issue", json={}, headers=self.wrong_tax_id_header())
        assert res.status_code == HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_wrong_api_token(self, app: FastAPI, client: AsyncClient) -> None:
        res = await client.post("/invoice/issue", json={}, headers=self.wrong_api_key_header())
        assert res.status_code == HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_wrong_country_code(self, app: FastAPI, client: AsyncClient) -> None:
        res = await client.post("/invoice/issue", json={}, headers=self.wrong_country_code_header())
        assert res.status_code == HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_correct_headers(self, app: FastAPI, client: AsyncClient) -> None:
        res = await client.post("/invoice/issue", json={}, headers=self.correct_headers())
        assert res.status_code != HTTP_403_FORBIDDEN

    def correct_headers(self):
        headers = {
            'x-tax-id': '1000522479',
            'x-api-token': '1000522479',
            'x-tax-country-code': 'UG',
            'x-api-key-header': '635f1ee-3493-407d-8ac8-8afd21a88795',
            'Content-Type': 'application/json'
        }
        return headers

    def wrong_tax_id_header(self):
        headers = {
            'x-tax-id': '10005224791',
            'x-api-token': '1000522479',
            'x-tax-country-code': 'UG',
            'x-api-key-header': '635f1ee-3493-407d-8ac8-8afd21a88795',
            'Content-Type': 'application/json'
        }
        return headers

    def wrong_api_key_header(self):
        headers = {
            'x-tax-id': '1000522479',
            'x-api-token': '1000522479',
            'x-tax-country-code': 'UG',
            'x-api-key-header': '635f1ee-3493-407d-8ac8-8afd21a887951',
            'Content-Type': 'application/json'
        }
        return headers

    def wrong_country_code_header(self):
        headers = {
            'x-tax-id': '1000522479',
            'x-api-token': '1000522479',
            'x-tax-country-code': 'UG',
            'x-api-key-header': '635f1ee-3493-407d-8ac8-8afd21a887951',
            'Content-Type': 'application/json'
        }
        return headers
