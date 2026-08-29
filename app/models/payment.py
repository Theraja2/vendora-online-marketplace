from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import PaymentStatus, values

if TYPE_CHECKING:
    from app.models.order import Order




class Payment(Base):
    __tablename__ = "payments"

    __table_args__ = (
        CheckConstraint(
            "status IN ('" + "', '".join(values(PaymentStatus)) + "')",
            name="ck_payments_status",
        ),
        CheckConstraint("amount >= 0", name="ck_payments_amount_non_negative"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey(
            "orders.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
        index=True
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=PaymentStatus.PENDING.value,
        server_default=PaymentStatus.PENDING.value,
        index=True
    )

    payment_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="mock"
    )

    transaction_reference: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="payment"
    )