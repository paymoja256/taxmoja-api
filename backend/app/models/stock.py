from sqlalchemy import Column, Integer, String, JSON, BigInteger
from sqlalchemy import Enum as SaEnum
from sqlalchemy.ext.declarative import declarative_base

from app.models.invoice import InvoiceStatuses

from app.core.config import Base


class Stock(Base):
    __tablename__ = "stock"
    id = Column(Integer, primary_key=True, index=True)
    commodity_tax_category_code = Column(String(255), index=True)
    commodity_tax_category_name = Column(String(255), index=True)
    goods_code = Column(String(255), index=True)
    goods_name = Column(String(255), index=True)
    goods_tax_id = Column(String(255), index=True)
    is_exempt = Column(String(255), index=True)
    is_zero_rate = Column(String(255), index=True)
    measure_unit = Column(String(255), index=True)
    tax_rate = Column(String(255), index=True)
    currency = Column(String(255), index=True)
    unit_price = Column(String(255), index=True)
    remarks = Column(String(255), index=True)
    client_id = Column(String(255), index=True)
    country_code = Column(String(255))
    request_data = Column(JSON)
    response_data = Column(JSON, nullable=True)
    quantity = Column(BigInteger)
    status = Column(SaEnum(InvoiceStatuses))

    _request_stock = None

    class Config:
        orm_mode = True

    @property
    def request_stock(self):
        return self._request_stock


class StockBranches(Base):
    __tablename__ = "stock_branches"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String(255), index=True)
    branch_name = Column(String(255))
    branch_id = Column(String(255))

    class Config:
        orm_mode = True
