from typing import List
import structlog

from fastapi import APIRouter, Depends, Request, HTTPException

from starlette.background import BackgroundTasks

from app.api.dependencies.database import get_database

from app.db.schemas.dear import DearProductBase, DearStockBase

from app.api.dependencies.authentication import get_url_tax_service

from app.api.dependencies.dear import Dear

struct_logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/{client_country}/{client_token}/{client_tax_pin}/stock/configuration", name="incoming dear"
                                                                                           ":create-stock_configuration")
async def dear_stock_configuration(product_details: List[DearProductBase],
                                   background_tasks: BackgroundTasks,
                                   client_tax_pin: str,
                                   client_country: str,
                                   client_token: str,
                                   db=Depends(get_database)):
    try:
        tax_service = get_url_tax_service(client_tax_pin, client_country, client_token)
        dear_service = Dear(tax_service.settings)

        struct_logger.info(event="stock_configuration_dear",
                           settings=tax_service.settings,
                           )

        stock_configuration_schema = dear_service.clean_stock_configuration_schema(product_details)

        struct_logger.info(event="stock_configuration_dear",
                           stock_configuration=stock_configuration_schema,
                           )

        stock_configuration_saved = tax_service.create_stock_configuration(db, stock_configuration_schema)

        async def send_new_stock_configuration():
            await tax_service.send_stock_configuration(db, stock_configuration_saved)

        background_tasks.add_task(send_new_stock_configuration)
        message = "Stock Configuration send for processing"

    except Exception as ex:
        raise HTTPException(status_code=404, detail=str(ex))

    return {"status_code": "200", "message": message}


@router.post("/{client_country}/{client_token}/{client_tax_pin}/stock/in", name="incoming dear "
                                                                                ":create-stock_adjustment")
async def dear_stock_adjustment(product_details: List[DearStockBase],
                                client_tax_pin: str,
                                client_country: str,
                                client_token: str,
                                session=Depends(get_database)
                                ):
    try:

        tax_service = get_url_tax_service(client_tax_pin, client_country, client_token)

        dear_service = Dear(tax_service.settings)

        struct_logger.info(event="stock_adjustment_dear",
                           settings=tax_service.settings,
                           )

        stock_adjustment_schema = dear_service.clean_stock_in_schema(product_details)

        struct_logger.info(event="stock_adjustment_dear",
                           stock_configuration=stock_adjustment_schema
                           )

        return await tax_service.send_goods_stock_adjustment(session, stock_adjustment_schema)

    except Exception as ex:
        struct_logger.error(event="stock_adjustment_dear",
                            error=ex
                            )

        raise HTTPException(status_code=500, detail=str(ex))


@router.post("/{client_country}/{client_token}/{client_tax_pin}/stock/adjustment",
             name="incoming dear :create-stock_adjustment detailed")
async def dear_stock_adjustment_detailed(request: Request,
                                         client_tax_pin: str,
                                         client_country: str,
                                         client_token: str,
                                         session=Depends(get_database)
                                         ):
    try:

        tax_service = get_url_tax_service(client_tax_pin, client_country, client_token)

        dear_service = Dear(tax_service.settings)

        struct_logger.info(event="stock_adjustment_dear",
                           settings=tax_service.settings,
                           request=request.body()
                           )

        product_details = await request.body()

        stock_adjustment_schema = dear_service.clean_stock_in_schema_detail(product_details)

        struct_logger.info(event="stock_adjustment_dear",
                           stock_configuration=stock_adjustment_schema
                           )

        return await tax_service.send_goods_stock_adjustment(session, stock_adjustment_schema)

    except Exception as ex:
        struct_logger.error(event="stock_adjustment_dear",
                            error=ex
                            )

        raise HTTPException(status_code=500, detail=str(ex))


@router.post("/{client_country}/{client_token}/{client_tax_pin}/invoice/issue")
async def dear_incoming_invoice(request: Request,
                                background_tasks: BackgroundTasks,
                                client_tax_pin: str,
                                client_country: str,
                                client_token: str,
                                session=Depends(get_database)):
    try:

        dear_invoice_details = await request.body()

        invoice_service = get_url_tax_service(client_tax_pin, client_country, client_token)

        dear_service = Dear(invoice_service.settings)

        struct_logger.info(event="dear_incoming_invoice",
                           dear_invoice=dear_invoice_details,
                           )

        incoming_invoice_schema = dear_service.clean_incoming_invoice_schema(dear_invoice_details)

        struct_logger.info(event="dear_incoming_invoice",
                           incoming_invoice_schema=incoming_invoice_schema
                           )

        message = invoice_service
        tax_invoice_saved = invoice_service.create_outgoing_invoice(session, incoming_invoice_schema)

        async def send_new_invoice():
            await invoice_service.send_invoice(session, tax_invoice_saved)

        background_tasks.add_task(send_new_invoice)
        message = "Invoice sent for processing"
    except Exception as ex:
        raise HTTPException(status_code=404, detail=str(ex))

    return {"status_code": "200", "message": message}


@router.post("/{client_country}/{client_token}/{client_tax_pin}/invoice/credit")
async def dear_credit_note(request: Request, background_tasks: BackgroundTasks,
                           client_tax_pin: str,
                           client_country: str,
                           client_token: str,
                           session=Depends(get_database)):
    response = await request.json()

    try:

        dear_invoice_details = await request.body()

        invoice_service = get_url_tax_service(client_tax_pin, client_country, client_token)

        dear_service = Dear(invoice_service.settings)

        struct_logger.info(event="dear_incoming_invoice",
                           bitrix_ivoice=dear_invoice_details,
                           )

        incoming_invoice_schema = dear_service.clean_incoming_credit_note_schema(dear_invoice_details)

        struct_logger.info(event="dear_incoming_invoice",
                           incoming_invoice_schema=incoming_invoice_schema
                           )

        message = invoice_service
        tax_invoice_saved = invoice_service.create_outgoing_invoice(session, incoming_invoice_schema)

        async def send_new_invoice():
            await invoice_service.send_invoice(session, tax_invoice_saved)

        background_tasks.add_task(send_new_invoice)
        message = "Invoice sent for processing"
    except Exception as ex:
        raise HTTPException(status_code=404, detail=str(ex))

    return {"status_code": "200", "message": message}



