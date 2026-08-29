from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """A paginated result set.

    `total` is the number of rows matching the filters, ignoring limit/offset,
    so a client can render page controls without a second request.
    """

    items: list[T]
    total: int
    limit: int
    offset: int
