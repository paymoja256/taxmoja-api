import structlog
from fastapi import APIRouter, Depends, Request, HTTPException
from starlette.background import BackgroundTasks

from app.api.dependencies.database import get_database
from app.api.dependencies.authentication import get_url_tax_service
from app.api.dependencies.bitrix import Bitrix24Mota

struct_logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/{client_country}/{client_token}/{client_tax_pin}/stock/configuration", name="incoming bitrix24 "
                                                                                           ":create-stock_configuration")
async def bitrix_stock_configuration(request: Request,
                                     background_tasks: BackgroundTasks,
                                     client_tax_pin: str,
                                     client_country: str,
                                     client_token: str,
                                     db=Depends(get_database)
                                     ):
    try:
        product_details = await request.body()

        tax_service = get_url_tax_service(client_tax_pin, client_country, client_token)

        bitrix_24 = Bitrix24Mota(tax_service.settings)

        struct_logger.info(event="stock_configuration_bitrix24",
                           settings=tax_service.settings,
                           )

        stock_configuration_schema = bitrix_24.clean_stock_configuration_schema(product_details)

        struct_logger.info(event="stock_configuration_bitrix24",
                           stock_configuration=stock_configuration_schema,
                           )

        stock_configuration_saved = tax_service.create_stock_configuration(db, stock_configuration_schema)

        async def send_new_stock_configuration():
            await tax_service.send_stock_configuration(db, stock_configuration_saved)

        background_tasks.add_task(send_new_stock_configuration)
        message = "Stock Configuration sent for processing"

        stock_adjustment_schema = bitrix_24.clean_stock_in_schema(product_details)

        struct_logger.info(event="stock_adjustment_bitrix24",
                           stock_adjustment=stock_adjustment_schema
                           )

        async def send_new_stock_adjustment():
            await tax_service.send_goods_stock_adjustment(db, stock_adjustment_schema)

        background_tasks.add_task(send_new_stock_adjustment)
        message = "Stock Configuration and  Adjustment sent for processing"

    except Exception as ex:
        raise HTTPException(status_code=404, detail=str(ex))

    return {"status_code": "200", "message": message}


@router.post("/{client_country}/{client_token}/{client_tax_pin}/stock/in", name="incoming bitrix24 "
                                                                                ":create-stock_adjustment")
async def bitrix_stock_adjustment(request: Request,
                                  client_tax_pin: str,
                                  client_country: str,
                                  client_token: str,
                                  session=Depends(get_database)):
    """Increase stock in EFRIS"""
    try:
        product_details = await request.body()

        tax_service = get_url_tax_service(client_tax_pin, client_country, client_token)

        bitrix_24 = Bitrix24Mota(tax_service.settings)

        struct_logger.info(event="stock_adjustment_bitrix24",
                           settings=tax_service.settings,
                           )

        stock_adjustment_schema = bitrix_24.clean_stock_in_schema(product_details, stock_in_type='102')

        struct_logger.info(event="stock_adjustment_bitrix24",
                           stock_configuration=stock_adjustment_schema
                           )

        return await tax_service.send_goods_stock_adjustment(session, stock_adjustment_schema)

    except Exception as ex:
        struct_logger.error(event="stock_adjustment_bitrix24",
                            error=ex
                            )

        raise HTTPException(status_code=500, detail=str(ex))


@router.post("/{client_country}/{client_token}/{client_tax_pin}/invoice/issue", name="incoming bitrix24"
                                                                                           ":create-invoice")
async def bitrix_incoming_invoice(request: Request, background_tasks: BackgroundTasks,
                                  client_tax_pin: str,
                                  client_country: str,
                                  client_token: str,
                                  session=Depends(get_database)):
    try:

        bitrix_invoice_details = await request.body()

        invoice_service = get_url_tax_service(client_tax_pin, client_country, client_token)

        bitrix_24 = Bitrix24Mota(invoice_service.settings)

        struct_logger.info(event="bitrix_incoming_invoice",
                           bitrix_invoice=bitrix_invoice_details,
                           )

        incoming_invoice_schema = bitrix_24.clean_incoming_invoice_schema(bitrix_invoice_details)

        struct_logger.info(event="bitrix_incoming_invoice",
                           incoming_invoice_schema=incoming_invoice_schema,
                           invoice_service=invoice_service
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
async def bitrix_incoming_credit_note(request: Request, background_tasks: BackgroundTasks,
                                      client_tax_pin: str,
                                      client_country: str,
                                      client_token: str,
                                      session=Depends(get_database)):
    try:

        bitrix_invoice_details = await request.body()

        invoice_service = get_url_tax_service(client_tax_pin, client_country, client_token)

        bitrix_24 = Bitrix24Mota(invoice_service.settings)

        struct_logger.info(event="bitrix_incoming_invoice",
                           bitrix_ivoice=bitrix_invoice_details,
                           )

        incoming_invoice_schema = bitrix_24.clean_incoming_invoice_schema(bitrix_invoice_details)

        struct_logger.info(event="bitrix_incoming_invoice",
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
