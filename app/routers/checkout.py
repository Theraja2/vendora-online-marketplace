from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_current_user
from app.schemas.checkout import (
    CheckoutResponse,
    PaymentCheckoutResponse,
)
from app.services.checkout_service import (
    prepare_checkout,
    process_checkout_payment,
)


router = APIRouter(
    prefix="/checkout",
    tags=["Checkout"],
)


@router.post(
    "",
    response_model=CheckoutResponse,
    status_code=status.HTTP_200_OK,
)
async def prepare_customer_checkout(
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    try:
        (
            cart_id,
            total_amount,
            item_count,
        ) = await prepare_checkout(
            session=session,
            user_id=current_user.id,
        )

        return {
            "message": (
                "Cart is valid and ready "
                "for checkout."
            ),
            "cart_id": cart_id,
            "total_amount": total_amount,
            "item_count": item_count,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post(
    "/payment",
    response_model=PaymentCheckoutResponse,
    status_code=status.HTTP_200_OK,
)
async def make_checkout_payment(
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    try:
        payment_result = await process_checkout_payment(
            session=session,
            user_id=current_user.id,
        )

        if not payment_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=payment_result.message,
            )

        return {
            "success": payment_result.success,
            "payment_reference": payment_result.reference,
            "amount": payment_result.amount,
            "message": payment_result.message,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )



