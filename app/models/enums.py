from enum import StrEnum


class Role(StrEnum):
    CUSTOMER = "customer"
    SELLER = "seller"
    ADMIN = "admin"


class Availability(StrEnum):
    IN_STOCK = "IN_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"

    @classmethod
    def from_inventory(cls, inventory: int) -> "Availability":
        return cls.IN_STOCK if inventory > 0 else cls.OUT_OF_STOCK


class OrderStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


def values(enum_cls: type[StrEnum]) -> list[str]:
    """Allowed values, for building CHECK constraints."""
    return [member.value for member in enum_cls]
