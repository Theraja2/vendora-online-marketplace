from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import get_current_user
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.review import Review
from app.models.user import User
from app.schemas.review import ReviewCreate, ReviewResponse


router = APIRouter(
    prefix="/reviews",
    tags=["Reviews"]
)


@router.post(
    "",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_review(
    review_data: ReviewCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    product_result = await session.execute(
        select(Product).where(
            Product.id == review_data.product_id
        )
    )

    product = product_result.scalar_one_or_none()

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    purchase_result = await session.execute(
        select(OrderItem)
        .join(
            Order,
            OrderItem.order_id == Order.id
        )
        .where(
            Order.user_id == current_user.id,
            OrderItem.product_id == review_data.product_id,
        )
    )

    purchased_item = purchase_result.scalar_one_or_none()

    if purchased_item is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only review products you have purchased",
        )

    existing_review_result = await session.execute(
        select(Review).where(
            Review.user_id == current_user.id,
            Review.product_id == review_data.product_id,
        )
    )

    existing_review = existing_review_result.scalar_one_or_none()

    if existing_review is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already reviewed this product",
        )

    review = Review(
        user_id=current_user.id,
        product_id=review_data.product_id,
        rating=review_data.rating,
        comment=review_data.comment,
    )

    session.add(review)

    try:
        await session.commit()

    except Exception:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to create review",
        )

    await session.refresh(review)

    return review