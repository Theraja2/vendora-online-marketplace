from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import require_roles
from app.models.category import Category
from app.models.enums import Availability, Role
from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.seller import Seller
from app.models.user import User
from app.schemas.common import Page
from app.schemas.product import (
    ProductCreate,
    ProductImageCreate,
    ProductImageResponse,
    ProductResponse,
    ProductUpdate,
)

router = APIRouter(
    prefix="/products",
    tags=["Products"],
)


SortField = Literal["created_at", "price", "name"]


async def _approved_seller_or_403(
    current_user: User,
    db: AsyncSession,
) -> Seller:
    """Resolve the caller's seller profile, rejecting unapproved accounts."""

    seller = await db.scalar(
        select(Seller).where(Seller.user_id == current_user.id)
    )

    if seller is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Seller profile not found",
        )

    if not seller.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seller account has not been approved",
        )

    return seller


async def _owned_product_or_403(
    product_id: int,
    seller: Seller,
    db: AsyncSession,
) -> Product:
    product = await db.scalar(
        select(Product).where(Product.id == product_id)
    )

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    if product.seller_id != seller.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only modify your own products",
        )

    return product


async def _active_category_or_404(
    category_id: int,
    db: AsyncSession,
) -> Category:
    category = await db.scalar(
        select(Category).where(
            Category.id == category_id,
            Category.is_active.is_(True),
        )
    )

    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active category not found",
        )

    return category


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_product(
    product_data: ProductCreate,
    current_user: User = Depends(require_roles(Role.SELLER.value)),
    db: AsyncSession = Depends(get_session),
) -> Product:

    seller = await _approved_seller_or_403(current_user, db)

    await _active_category_or_404(product_data.category_id, db)

    product = Product(
        seller_id=seller.id,
        category_id=product_data.category_id,
        name=product_data.name,
        description=product_data.description,
        price=product_data.price,
        inventory=product_data.inventory,
        availability=Availability.from_inventory(product_data.inventory).value,
    )

    db.add(product)

    await db.commit()

    await db.refresh(product)

    return product


@router.get(
    "",
    response_model=Page[ProductResponse],
)
async def list_products(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    category_id: int | None = Query(default=None, gt=0),
    search: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
        description="Case-insensitive match against the product name.",
    ),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    in_stock_only: bool = Query(default=False),
    sort_by: SortField = Query(default="created_at"),
    sort_dir: Literal["asc", "desc"] = Query(default="desc"),
    db: AsyncSession = Depends(get_session),
) -> Page[ProductResponse]:
    """Browse the catalogue.

    Only products in an active category are visible. Every filter is optional and
    they combine with AND.
    """

    filters = [Category.is_active.is_(True)]

    if category_id is not None:
        filters.append(Product.category_id == category_id)

    if search:
        # ilike is case-insensitive on PostgreSQL; SQLAlchemy emits lower(...) LIKE
        # for backends without it, so this behaves the same in the test suite.
        filters.append(Product.name.ilike(f"%{search}%"))

    if min_price is not None:
        filters.append(Product.price >= min_price)

    if max_price is not None:
        filters.append(Product.price <= max_price)

    if in_stock_only:
        filters.append(Product.inventory > 0)

    total = await db.scalar(
        select(func.count())
        .select_from(Product)
        .join(Category, Product.category_id == Category.id)
        .where(*filters)
    )

    sort_column = {
        "created_at": Product.created_at,
        "price": Product.price,
        "name": Product.name,
    }[sort_by]

    ordering = sort_column.asc() if sort_dir == "asc" else sort_column.desc()

    result = await db.execute(
        select(Product)
        .join(Category, Product.category_id == Category.id)
        .where(*filters)
        # id breaks ties so pagination stays stable across pages.
        .order_by(ordering, Product.id.desc())
        .limit(limit)
        .offset(offset)
    )

    return Page[ProductResponse](
        items=[ProductResponse.model_validate(p) for p in result.scalars().all()],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_session),
) -> Product:

    product = await db.scalar(
        select(Product)
        .join(Category, Product.category_id == Category.id)
        .where(
            Product.id == product_id,
            Category.is_active.is_(True),
        )
    )

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    return product


@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
)
async def update_product(
    product_id: int,
    product_data: ProductUpdate,
    current_user: User = Depends(require_roles(Role.SELLER.value)),
    db: AsyncSession = Depends(get_session),
) -> ProductResponse:

    seller = await _approved_seller_or_403(current_user, db)

    product = await _owned_product_or_403(product_id, seller, db)

    if product_data.category_id is not None:
        await _active_category_or_404(product_data.category_id, db)

    update_data = product_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(product, field, value)

    product.availability = Availability.from_inventory(product.inventory).value

    await db.commit()

    await db.refresh(product)

    return product


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_product(
    product_id: int,
    current_user: User = Depends(require_roles(Role.SELLER.value)),
    db: AsyncSession = Depends(get_session),
) -> None:

    seller = await _approved_seller_or_403(current_user, db)

    product = await _owned_product_or_403(product_id, seller, db)

    await db.delete(product)

    await db.commit()


@router.post(
    "/{product_id}/images",
    response_model=ProductImageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_product_image(
    product_id: int,
    image_data: ProductImageCreate,
    current_user: User = Depends(require_roles(Role.SELLER.value)),
    db: AsyncSession = Depends(get_session),
) -> ProductImageResponse:

    seller = await _approved_seller_or_403(current_user, db)

    await _owned_product_or_403(product_id, seller, db)

    if image_data.is_primary:
        # Demote every existing primary in one statement. The previous version
        # read a single row with scalar_one_or_none(), which raised
        # MultipleResultsFound -- a permanent 500 -- the moment two primaries
        # existed. A partial unique index on (product_id) WHERE is_primary now
        # makes that state impossible in the first place.
        await db.execute(
            update(ProductImage)
            .where(
                ProductImage.product_id == product_id,
                ProductImage.is_primary.is_(True),
            )
            .values(is_primary=False)
        )

        await db.flush()

    image = ProductImage(
        product_id=product_id,
        image_url=str(image_data.image_url),
        is_primary=image_data.is_primary,
        sort_order=image_data.sort_order,
    )

    db.add(image)

    try:
        await db.commit()
    except IntegrityError as exc:
        # Two concurrent primary uploads: the index rejects the loser instead of
        # letting a second primary through.
        await db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another primary image was set for this product. Please retry.",
        ) from exc

    await db.refresh(image)

    return image


@router.get(
    "/{product_id}/images",
    response_model=list[ProductImageResponse],
)
async def list_product_images(
    product_id: int,
    db: AsyncSession = Depends(get_session),
) -> list[ProductImageResponse]:

    product = await db.scalar(
        select(Product).where(Product.id == product_id)
    )

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    result = await db.execute(
        select(ProductImage)
        .where(ProductImage.product_id == product_id)
        .order_by(
            ProductImage.sort_order.asc(),
            ProductImage.created_at.asc(),
        )
    )

    return list(result.scalars().all())


@router.delete(
    "/{product_id}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_product_image(
    product_id: int,
    image_id: int,
    current_user: User = Depends(require_roles(Role.SELLER.value)),
    db: AsyncSession = Depends(get_session),
) -> None:

    seller = await _approved_seller_or_403(current_user, db)

    await _owned_product_or_403(product_id, seller, db)

    image = await db.scalar(
        select(ProductImage).where(
            ProductImage.id == image_id,
            ProductImage.product_id == product_id,
        )
    )

    if image is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )

    await db.delete(image)

    await db.commit()
