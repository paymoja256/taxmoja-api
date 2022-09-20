import structlog
from sqlalchemy.orm import Session

from app.models.invoice import InvoiceStatuses
from app.models.stock import Stock, StockBranches
from app.db.schemas.stock import IncomingStockConfigurationSchema, BranchSchema

struct_logger = structlog.get_logger(__name__)


def create_stock(
        session: Session,
        stock: IncomingStockConfigurationSchema,
        country_code,
        tax_id
):
    try:

        stock_exists = get_stock_by_goods_code(session, stock.goods_code)

        if not stock_exists:
            new_stock_details = {
                "goods_name": stock.goods_name,
                "goods_code": stock.goods_code,
                "unit_price": stock.unit_price,
                "measure_unit": stock.measure_unit,
                "currency": stock.currency,
                "commodity_tax_category": stock.commodity_tax_category,
                "goods_description": stock.goods_description,
                "status": InvoiceStatuses.RECEIVED
            }

            stock_base = IncomingStockConfigurationSchema(**new_stock_details)
            new_stock = save_stock_configuration(session, stock_base, country_code, tax_id)
            new_stock._request_stock = stock
            return new_stock

        return stock_exists

    except Exception as ex:

        struct_logger.error(event="create_outgoing_invoice", error="Failed to save invoice", message=str(ex))

        return None


def save_stock_configuration(session: Session, stock_details: IncomingStockConfigurationSchema, country_code, tax_id):

    new_stock = Stock(commodity_tax_category_code=stock_details.commodity_tax_category,
                      commodity_tax_category_name=None,
                      goods_code=stock_details.goods_code,
                      goods_name=stock_details.goods_name,
                      measure_unit=stock_details.measure_unit,
                      currency=stock_details.currency,
                      unit_price=stock_details.unit_price,
                      remarks=stock_details.goods_description,
                      client_id=tax_id,
                      country_code=country_code,
                      request_data=stock_details.json(),
                      status=InvoiceStatuses.RECEIVED
                      )
    with session.begin() as db:
        db.add(new_stock)
        db.expunge_all()

    return new_stock


def save_stock(session: Session, stock: Stock):
    with session.begin() as db:
        db.add(stock)
        db.expunge_all()


def get_stock_by_goods_code(session: Session, goods_code: str):
    with session.begin() as db:
        query= db.query(Stock).filter(Stock.goods_code == goods_code).first()
        db.expunge_all()

        return query


def create_stock_branch(session: Session, branch: BranchSchema):
    new_branch = StockBranches(
        client_id=branch.client_id,
        branch_name=branch.branch_name,
        branch_id=branch.branch_id
    )
    with session.begin() as db:
        db.add(new_branch)
        db.expunge_all()

    return new_branch


def get_branch_by_client_id(session: Session, client_id: str):
    with session.begin() as db:
        query= db.query(StockBranches).filter(StockBranches.client_id == client_id).first()
        db.expunge_all()

        return query
