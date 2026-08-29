from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import Availability, values

if TYPE_CHECKING:
    from app.models.cart_item import CartItem
    from app.models.category import Category
    from app.models.order_item import OrderItem
    from app.models.product_image import ProductImage
    from app.models.review import Review
    from app.models.seller import Seller



class Product(Base):
    __tablename__ = "products"

    __table_args__ = (
        CheckConstraint("price > 0", name="ck_products_price_positive"),
        CheckConstraint("inventory >= 0", name="ck_products_inventory_non_negative"),
        CheckConstraint(
            "availability IN ('" + "', '".join(values(Availability)) + "')",
            name="ck_products_availability",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    seller_id: Mapped[int] = mapped_column(
        ForeignKey(
            "sellers.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    category_id: Mapped[int] = mapped_column(
        ForeignKey(
            "categories.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False
    )

    inventory: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    availability: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=Availability.OUT_OF_STOCK.value,
        server_default=Availability.OUT_OF_STOCK.value,
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

    # -------------------------
    # Relationships
    # -------------------------

    seller: Mapped["Seller"] = relationship(
        "Seller",
        back_populates="products"
    )

    category: Mapped["Category"] = relationship(
        "Category",
        back_populates="products"
    )

    # passive_deletes lets the database's ON DELETE CASCADE remove these rows.
    # Without it SQLAlchemy tries to de-associate the children first by setting
    # their product_id to NULL, which the NOT NULL constraint rejects -- deleting
    # any product that had images failed with a 500.
    product_images: Mapped[list["ProductImage"]] = relationship(
        "ProductImage",
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    cart_items: Mapped[list["CartItem"]] = relationship(
        "CartItem",
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # NOTE: the foreign key declares ON DELETE CASCADE, so deleting a product
    # also removes it from historical orders. If order history must survive,
    # change this FK to RESTRICT and soft-delete products instead.
    order_items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="product",
        passive_deletes=True,
    )

    reviews: Mapped[list["Review"]] = relationship(
        "Review",
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )