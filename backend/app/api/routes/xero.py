from typing import Union
import structlog
from fastapi import APIRouter, Depends, Request, HTTPException, Header
from starlette import status
from starlette.background import BackgroundTasks
from app.api.dependencies.database import get_database
from app.api.dependencies.authentication import get_url_tax_service
from app.api.dependencies.xero import XeroHelper
from starlette.responses import Response

struct_logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/{client_country}/{client_token}/{client_tax_pin}/invoice/issue", name="incoming xero"
                                                                                     ":create-new-invoice")
async def xero_incoming_invoice(request: Request, background_tasks: BackgroundTasks,
                                client_tax_pin: str,
                                client_country: str,
                                client_token: str,
                                x_xero_signature: Union[str, None] = Header(default=None, convert_underscores=True),
                                session=Depends(get_database),
                                status_code=status.HTTP_201_CREATED):
    try:

        xero_invoice_details = await request.body()

        invoice_service = get_url_tax_service(client_tax_pin, client_country, client_token)

        xero_service = XeroHelper(invoice_service.settings)

        struct_logger.info(event="xero_incoming_invoice",
                           xero_invoice=xero_invoice_details,


                           )

        is_payload_valid = xero_service.validate_payload(xero_invoice_details)

        status_code = 200 if is_payload_valid else 401

        # incoming_invoice_schema = xero_service.clean_incoming_invoice_schema(xero_invoice_details)
        #
        # struct_logger.info(event="xero_incoming_invoice",
        #                    incoming_invoice_schema=incoming_invoice_schema,
        #                    invoice_service=invoice_service
        #                    )

        # message = invoice_service
        # tax_invoice_saved = invoice_service.create_outgoing_invoice(session, incoming_invoice_schema)
        #
        # async def send_new_invoice():
        #     await invoice_service.send_invoice(session, tax_invoice_saved)
        #
        # background_tasks.add_task(send_new_invoice)
        message = "Invoice sent for processing"
    except Exception as ex:

        struct_logger.info(event="xero_incoming_invoice",
                           error=str(ex)
                           )
        raise HTTPException(status_code=404, detail=str(ex))

    return Response(status_code=status_code)


@router.post("/{client_country}/{client_token}/{client_tax_pin}/invoice/credit", name="incoming xero"
                                                                                      ":create-credit_note")
async def xero_incoming_credit_note(request: Request, background_tasks: BackgroundTasks,
                                    client_tax_pin: str,
                                    client_country: str,
                                    client_token: str,
                                    session=Depends(get_database)):
    try:

        xero_invoice_details = await request.body()

        invoice_service = get_url_tax_service(client_tax_pin, client_country, client_token)

        xero_service = XeroHelper(invoice_service.settings)

        struct_logger.info(event="xero_incoming_invoice",
                           xero_invoice=xero_invoice_details,
                           )

        incoming_invoice_schema = xero_service.clean_incoming_invoice_schema(xero_invoice_details)

        struct_logger.info(event="xero_incoming_invoice",
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
