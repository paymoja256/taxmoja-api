import structlog
from fastapi.responses import HTMLResponse
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Header
from fastapi.templating import Jinja2Templates
from app.db.schemas.invoice import TaxInvoiceIncomingSchema, CreditNoteCancelSchema
from app.api.dependencies.authentication import get_tax_service
from app.api.dependencies.database import get_database
from app.db.schemas.stock import IncomingGoodsStockAdjustmentSchema
from app.db.schemas.stock import IncomingStockConfigurationSchema
from app.api.dependencies.common import change_keys, convert


router = APIRouter()

struct_logger = structlog.get_logger(__name__)


@router.post("/stock/configuration")
async def incoming_stock_configuration(
    stock_configuration: IncomingStockConfigurationSchema,
    background_tasks: BackgroundTasks,
    session=Depends(get_database),
    stock_service=Depends(get_tax_service),
):
    try:
        stock_configuration_saved = stock_service.create_stock_configuration(
            session, stock_configuration
        )

        message = await stock_service.send_stock_configuration(
            session, stock_configuration_saved
        )

        status_code = "200"
    except Exception as ex:
        message = str(ex)
        status_code = "500"

    return {"status_code": status_code, "message": message}


@router.post("/stock/adjustment")
async def incoming_stock_adjustment(
    stock_detail: IncomingGoodsStockAdjustmentSchema,
    background_tasks: BackgroundTasks,
    session=Depends(get_database),
    stock_service=Depends(get_tax_service),
):
    try:
        message = await stock_service.send_goods_stock_adjustment(session, stock_detail)
        status_code = "200"
    except Exception as ex:
        message = str(ex)
        status_code = "500"

    return {"status_code": status_code, "message": message}


@router.post("/invoice/issue", name="incoming tax invoices:create-invoice")
async def incoming_invoice(
    tax_invoice: TaxInvoiceIncomingSchema,
    invoice_service=Depends(get_tax_service),
    session=Depends(get_database),
    erp: str = ''
):
    try:
        message = invoice_service
        tax_invoice_saved = invoice_service.create_outgoing_invoice(
            session, tax_invoice
        )

        message = await invoice_service.send_invoice(session, tax_invoice_saved, erp)
    except Exception as ex:
        raise HTTPException(status_code=404, detail=str(ex))

    return {"status_code": "200", "message": message}


@router.post("/invoice/queue", name="incoming tax invoices:queue-invoice")
async def incoming_invoice_queue(
    tax_invoice: TaxInvoiceIncomingSchema,
    background_tasks: BackgroundTasks,
    invoice_service=Depends(get_tax_service),
    session=Depends(get_database),
    erp: str = ''
):
    try:
        message = invoice_service
        tax_invoice_saved = invoice_service.create_outgoing_invoice(
            session, tax_invoice
        )

        async def send_new_invoice():
            await invoice_service.send_invoice(session, tax_invoice_saved, erp)

        background_tasks.add_task(send_new_invoice)
        message = "invoice sent for processing"
    except Exception as ex:
        raise HTTPException(status_code=404, detail=str(ex))

    return {"status_code": "200", "message": message}


@router.post("/credit-note/cancel", name="incoming tax invoices:cancel credit notes")
async def cancel_credit_note(
    tax_invoice: CreditNoteCancelSchema,
    background_tasks: BackgroundTasks,
    invoice_service=Depends(get_tax_service),
    session=Depends(get_database),
):
    try:
        message = invoice_service

        message = await invoice_service.cancel_invoice(session, tax_invoice)

    except Exception as ex:
        raise HTTPException(status_code=404, detail=str(ex))

    return {"status_code": "200", "message": message}


@router.get(
    "/invoice/query/{instance_invoice_id}", name="incoming tax invoices:query-invoice"
)
async def query_incoming_invoice(
    instance_invoice_id: str,
    session=Depends(get_database),
    tax_service=Depends(get_tax_service),
):
    try:
        request_data = await tax_service.get_invoice_query_by_instance_id(
            session, instance_invoice_id
        )

        struct_logger.info(
            event="retrieved invoice from database", message=request_data
        )

        return request_data
    except Exception as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@router.get(
    "/creditnote/query", name="credit note:query-credit note"
)
async def query_credit_notes(
    tax_service=Depends(get_tax_service),
):
    try:
        request_data = await tax_service.query_credit_notes()

        struct_logger.info(
            event="Query credit notes", message=request_data
        )

        return request_data
    except Exception as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@router.get("/information/{information_request}")
async def incoming_information_request(
    information_request: str,
    information_service=Depends(get_tax_service),
):
    try:
      
        message = await information_service.incoming_information_request(
            information_request
        )

    except Exception as ex:
        raise HTTPException(status_code=404, detail=str(ex))

    return {"status_code": "200", "message": message}


@router.get("/invoice/print/{instance_invoice_id}", response_class=HTMLResponse)
async def print_invoice(
    instance_invoice_id: str,
    session=Depends(get_database),
    x_tax_country_code=Header(...),
    tax_service=Depends(get_tax_service),
    x_tax_id: str = Header(...),
):
    try:
        printed_invoice = await tax_service.get_invoice_by_id(
            session, instance_invoice_id
        )
        struct_logger.info(
            event="retrieved invoice from database", message=printed_invoice
        )
        invoice_data = {**printed_invoice.request_data,
                        **printed_invoice.response_data}

        from pathlib import Path

        backend = Path().absolute()

        jinja_templates = Jinja2Templates(
            directory=f"{backend}/app/api/static/templates"
        )

        invoice_data = change_keys(invoice_data, convert)

        struct_logger.info(event="print_invoice", message=invoice_data)

        return jinja_templates.TemplateResponse(
            "/invoices/invoice_template_{}.html".format(
                x_tax_country_code.lower()),
            {
                "request": invoice_data,
                "tax_pin": x_tax_id,
                "instance_invoice_id": printed_invoice.instance_invoice_id,
            },
        )

    except Exception as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@router.get("/credit/print/{instance_invoice_id}", response_class=HTMLResponse)
async def print_credit_note(
    instance_invoice_id: str,
    session=Depends(get_database),
    x_tax_country_code=Header(...),
    tax_service=Depends(get_tax_service),
    x_tax_id: str = Header(...),
):
    try:
        request_data = await tax_service.get_invoice_by_instance_id(
            session, instance_invoice_id
        )

        struct_logger.info(
            event="retrieved invoice from database", message=request_data
        )
        invoice_data = {**request_data, **request_data}

        from pathlib import Path

        backend = Path().absolute()

        jinja_templates = Jinja2Templates(
            directory=f"{backend}/app/api/static/templates"
        )

        invoice_data = change_keys(invoice_data, convert)

        struct_logger.info(event="print_invoice", message=invoice_data)

        return jinja_templates.TemplateResponse(
            "/invoices/invoice_template_{}.html".format(
                x_tax_country_code.lower()),
            {
                "request": invoice_data,
                "tax_pin": x_tax_id,
                "instance_invoice_id": instance_invoice_id,
            },
        )

    except Exception as ex:
        raise HTTPException(status_code=404, detail=str(ex))
