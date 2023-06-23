import structlog
from sqlalchemy.orm import sessionmaker

from app.models.invoice import TaxInvoiceOutgoing, InvoiceStatuses, \
    TaxInvoiceNumber
from app.db.schemas.invoice import TaxInvoiceIncomingSchema, TaxInvoiceOutgoingSchema, InvoiceNumberSchema

struct_logger = structlog.get_logger(__name__)


def create_outgoing_invoice(session: sessionmaker,
                            invoice: TaxInvoiceIncomingSchema,
                            country_code,
                            tax_id):
    '''
    Saves a raw invoice from upstream
    All the data gets jammed into 'request_data'
    status is RECEIVED
    The handler later takes this and converts it to integration specific representation
    (an outgoing tax invoice)
    '''

    try:

        invoice_exists = get_invoice(session, invoice.instance_invoice_id, country_code, tax_id)

        print("invoice exists: {}-{}".format(invoice_exists, invoice.instance_invoice_id))
         
        if not invoice_exists :
            new_invoice_details = {
                "request_data": invoice.json(),
                "country_code": country_code,
                "status": InvoiceStatuses.RECEIVED,
                "client_tin": tax_id,
                "instance_invoice_id": invoice.instance_invoice_id
            }

            invoice_base = TaxInvoiceOutgoingSchema(**new_invoice_details)
            new_invoice = create_invoice(session, invoice_base)
            new_invoice._request_invoice = invoice
            return "new invoice created", new_invoice
   
        else:
            with session.begin() as db:
                invoice_exists.request_data = invoice.json()
                invoice_exists.status = InvoiceStatuses.RECEIVED
                db.add(invoice_exists)
              
            return  "invoice exists", invoice_exists
        

    except Exception as ex:

        struct_logger.error(event="create_outgoing_invoice", error="Failed to save invoice", message=str(ex))

        return None


def create_invoice(session: sessionmaker, invoice_details: TaxInvoiceOutgoingSchema):
    new_invoice = TaxInvoiceOutgoing(
        invoice_code=invoice_details.invoice_code,
        instance_invoice_id=invoice_details.instance_invoice_id,
        client_tin=invoice_details.client_tin,
        related_invoice=invoice_details.related_invoice,
        request_data=invoice_details.request_data,
        response_data=invoice_details.response_data,
        country_code=invoice_details.country_code,
        upload_code=invoice_details.upload_code,
        upload_desc=invoice_details.upload_desc,
        status=invoice_details.status)
    with session.begin() as db:
        db.add(new_invoice)

    return new_invoice


def get_invoice(session: sessionmaker, instance_invoice_id: str, country_code: str, tax_id: str):
    with session.begin() as db:
        invoice = db.query(TaxInvoiceOutgoing).filter(
            TaxInvoiceOutgoing.instance_invoice_id == instance_invoice_id,
            TaxInvoiceOutgoing.country_code == country_code,
            TaxInvoiceOutgoing.client_tin == tax_id).one_or_none()
        return invoice


def save_invoice(session: sessionmaker, invoice: TaxInvoiceOutgoing):
    with session.begin() as db:
        db.add(invoice)


def create_invoice_number(session: sessionmaker, invoice_number_details: InvoiceNumberSchema):
    new_invoice_number = TaxInvoiceNumber(
        invoice_code=invoice_number_details.invoice_code,
        invoice_number=invoice_number_details.invoice_number,
        number_begin=invoice_number_details.number_begin,
        number_end=invoice_number_details.number_end,
        tax_id=invoice_number_details.tax_id
    )
    with session.begin() as db:
        db.add(new_invoice_number)
        db.expunge_all()

    return new_invoice_number


def update_invoice_number(session: sessionmaker, instance_invoice_id: str, tax_pin: str, invoice_code: str,
                          invoice_number: str):
    with session.begin() as db:
        used_invoice = db.query(TaxInvoiceNumber).filter(TaxInvoiceNumber.tax_id == tax_pin,
                                                         TaxInvoiceNumber.invoice_code == invoice_code,
                                                         TaxInvoiceNumber.invoice_number == invoice_number).one_or_none()

        db.expunge_all()

        if used_invoice is None:
            return None

        used_invoice.instance_invoice_id = instance_invoice_id
        db.add(used_invoice)

        return used_invoice


def get_invoice_blank_number(session: sessionmaker, tax_pin: str):
    with session.begin() as db:
        query = db.query(TaxInvoiceNumber).filter(TaxInvoiceNumber.tax_id == tax_pin,
                                                  TaxInvoiceNumber.instance_invoice_id == None).first()
        db.expunge_all()

        return query


def get_invoice_number_code(session: sessionmaker, tax_pin: str, invoice_code: str, number_begin: str):
    with session.begin() as db:
        query = db.query(TaxInvoiceNumber).filter(
            TaxInvoiceNumber.invoice_code == invoice_code, TaxInvoiceNumber.number_begin == number_begin,
            TaxInvoiceNumber.tax_id == tax_pin).first()

        db.expunge_all()

        return query


def get_invoice_by_code(session: sessionmaker, invoice_code: str):
    with session.begin() as db:
        query = db.query(TaxInvoiceOutgoing).filter(
            TaxInvoiceOutgoing.invoice_code == invoice_code and TaxInvoiceOutgoing.related_invoice == "").first()

        db.expunge_all()

        return query


def get_credit_note_by_code(session: sessionmaker, invoice_code: str):
    with session.begin() as db:
        query = db.query(TaxInvoiceOutgoing).filter(
            TaxInvoiceOutgoing.invoice_code == invoice_code and TaxInvoiceOutgoing.related_invoice != "").first()

        db.expunge_all()

        return query
