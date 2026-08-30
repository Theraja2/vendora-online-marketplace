from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, func, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import Role, values

if TYPE_CHECKING:
    from app.models.cart import Cart
    from app.models.order import Order
    from app.models.review import Review
    from app.models.seller import Seller
    

class User(Base):
    __tablename__ = "users"

    __table_args__ = (
        CheckConstraint(
            "role IN ('" + "', '".join(values(Role)) + "')",
            name="ck_users_role",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    username: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True
    )

    password: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    phone_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
        index=True
    )

    role: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=Role.CUSTOMER.value,
        server_default=Role.CUSTOMER.value,
        index=True
    )

    refresh_token: Mapped[str | None] = mapped_column(
    Text,
    nullable=True,
)

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # -------------------------
    # Relationships
    # -------------------------

    seller: Mapped["Seller | None"] = relationship(
        "Seller",
        back_populates="user",
        uselist=False
    )

    cart: Mapped["Cart | None"] = relationship(
        "Cart",
        back_populates="user",
        uselist=False,
        passive_deletes=True,
    )

    orders: Mapped[list["Order"]] = relationship(
        "Order",
        back_populates="user",
        passive_deletes=True,
    )

    reviews: Mapped[list["Review"]] = relationship(
        "Review",
        back_populates="user",
        passive_deletes=True,
    )