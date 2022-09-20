from sqlalchemy.orm import relationship
from sqlalchemy import Column, ForeignKey, String, JSON, DateTime, func, BigInteger
from sqlalchemy import Enum as SaEnum
from enum import Enum
from app.core.config import Base



class InvoiceStatuses(str, Enum):
    RECEIVED = 'RECEIVED'  # init state; received but not yet processed
    SENDING = 'SENDING'  # converted to integration and in process of being sent
    SENT = 'SENT'  # end state
    ERROR = 'ERROR'  # Could not be sent


class TaxInvoiceOutgoing(Base):
    __tablename__ = "tax_invoice_outgoing"

    id = Column(BigInteger, primary_key=True, index=True)
    invoice_code = Column(String(255), index=True, nullable=True)
    instance_invoice_id = Column(String(255), index=True, unique=True, nullable=True)
    client_tin = Column(String(255), index=True)
    related_invoice = Column(String(255), index=True, nullable=True)
    request_data = Column(JSON)
    response_data = Column(JSON, nullable=True)
    country_code = Column(String(255))
    upload_code = Column(String(255), index=True, nullable=True)
    upload_desc = Column(String(255), nullable=True)
    issue_date = Column(DateTime(timezone=True))
    date_last_modified = Column(DateTime(timezone=True))
    status = Column(SaEnum(InvoiceStatuses))
    tax_invoice_numbers = relationship("TaxInvoiceNumber", back_populates="tax_invoice_outgoing")

    _request_invoice = None

    class Config:
        orm_mode = True

    @property
    def request_invoice(self):
        return self._request_invoice


class TaxInvoiceNumber(Base):
    __tablename__ = "tax_invoice_numbers"

    id = Column(BigInteger, primary_key=True, index=True)
    invoice_code = Column(String(255), index=True)
    tax_id = Column(String(255), index=True)
    invoice_number = Column(String(255), index=True, nullable=True)
    number_begin = Column(String(255), index=True, nullable=True)
    number_end = Column(String(255), index=True, nullable=True)
    instance_invoice_id = Column(String(255), ForeignKey('tax_invoice_outgoing.instance_invoice_id'))
    issue_date = Column(DateTime(timezone=True))
    date_last_modified = Column(DateTime(timezone=True))
    date_added = Column(DateTime(timezone=True), index=True)
    tax_invoice_outgoing = relationship("TaxInvoiceOutgoing", back_populates="tax_invoice_numbers")

    class Config:
        orm_mode = True
