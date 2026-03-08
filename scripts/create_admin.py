"""Create an admin user interactively."""

import asyncio
import sys

sys.path.insert(0, "backend")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.security import hash_password
from app.models.organization import Organization
from app.models.user import User


async def create_admin():
    print("=== Create Admin User ===\n")

    email = input("Email: ").strip()
    password = input("Password: ").strip()
    first_name = input("First name: ").strip()
    last_name = input("Last name: ").strip()
    org_name = input("Organization name: ").strip()

    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        # Check if email exists
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            print(f"\nError: User with email {email} already exists!")
            return

        # Create or get organization
        from slugify import slugify

        slug = slugify(org_name)
        org_result = await db.execute(select(Organization).where(Organization.slug == slug))
        org = org_result.scalar_one_or_none()

        if not org:
            org = Organization(name=org_name, slug=slug)
            db.add(org)
            await db.flush()
            print(f"Created organization: {org_name}")

        user = User(
            organization_id=org.id,
            email=email,
            password_hash=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            role="admin",
        )
        db.add(user)
        await db.commit()

        print(f"\nAdmin user created: {email}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_admin())
