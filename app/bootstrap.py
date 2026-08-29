"""Startup tasks.

The first admin is a bootstrapping problem: every account created through
/auth/register is a customer, and only an admin can change anyone's role. So the
very first admin has to come from configuration rather than from the API.

Set FIRST_ADMIN_USERNAME and FIRST_ADMIN_PASSWORD in .env and this creates the
account on startup. It runs on every boot but only ever creates the account once,
so leaving the settings in place is harmless.
"""

import logging

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.enums import Role
from app.models.user import User
from app.security.password import hash_password

logger = logging.getLogger("app.bootstrap")


async def ensure_first_admin() -> None:
    if not settings.FIRST_ADMIN_USERNAME or not settings.FIRST_ADMIN_PASSWORD:
        logger.info(
            "No FIRST_ADMIN_USERNAME/FIRST_ADMIN_PASSWORD set -- skipping admin seeding."
        )
        return

    if len(settings.FIRST_ADMIN_PASSWORD) < 8:
        logger.error(
            "FIRST_ADMIN_PASSWORD must be at least 8 characters. Admin not created."
        )
        return

    try:
        async with AsyncSessionLocal() as db:
            existing = await db.scalar(
                select(User).where(
                    User.username == settings.FIRST_ADMIN_USERNAME
                )
            )

            if existing is not None:
                if existing.role != Role.ADMIN.value:
                    logger.warning(
                        "User %r exists but has role %r, not admin. "
                        "Leaving it alone -- promote it from another admin account.",
                        existing.username,
                        existing.role,
                    )
                return

            admin = User(
                full_name=settings.FIRST_ADMIN_FULL_NAME,
                username=settings.FIRST_ADMIN_USERNAME,
                email=settings.FIRST_ADMIN_EMAIL,
                phone_number=settings.FIRST_ADMIN_PHONE,
                password=hash_password(settings.FIRST_ADMIN_PASSWORD),
                role=Role.ADMIN.value,
                is_active=True,
            )

            db.add(admin)
            await db.commit()

        logger.warning(
            "Created the first admin account %r. Log in and change its password, "
            "then clear FIRST_ADMIN_PASSWORD from .env.",
            settings.FIRST_ADMIN_USERNAME,
        )

    except Exception:
        # A missing table is the usual cause, and crashing here would hide it
        # behind a raw SQL error. Say what to do instead.
        logger.exception(
            "Could not create the first admin. If the tables do not exist yet, "
            "run 'alembic upgrade head' and restart."
        )
