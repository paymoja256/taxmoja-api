import pytest
from httpx import AsyncClient
from fastapi import FastAPI

from starlette.status import HTTP_404_NOT_FOUND, HTTP_422_UNPROCESSABLE_ENTITY


class TestTaxesRoutes:


    @pytest.mark.asyncio
    async def test_create_invoice_route_exists(self, app: FastAPI, client: AsyncClient) -> None:
        res = await client.post("/invoice/issue", json={})
        assert res.status_code != HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_create_invoice_invalid_input_raises_error(self, app: FastAPI, client: AsyncClient) -> None:
        res = await client.post("/invoice/issue", json={})
        assert res.status_code == HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_stock_adjustment_routes_exist(self, app: FastAPI, client: AsyncClient) -> None:
        res = await client.post("/stock/adjustment", json={})
        assert res.status_code != HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_stock_adjustment_routes_invalid_input_raises_error(self, app: FastAPI, client: AsyncClient) -> None:
        res = await client.post("/stock/adjustment", json={})
        assert res.status_code == HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_stock_configuration_routes_exist(self, app: FastAPI, client: AsyncClient) -> None:
        res = await client.post("/stock/configuration", json={})
        assert res.status_code != HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_stock_configuration_invalid_input_raises_error(self, app: FastAPI, client: AsyncClient) -> None:
        res = await client.post("/stock/configuration", json={})
        assert res.status_code == HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_information_routes_exist(self, app: FastAPI, client: AsyncClient) -> None:
        res = await client.get("/information/heartbeat")
        assert res.status_code != HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_information_routes_invalid_input_raises_error(self, app: FastAPI, client: AsyncClient) -> None:
        res = await client.get("/information/heartbeat")
        assert res.status_code == HTTP_422_UNPROCESSABLE_ENTITY
