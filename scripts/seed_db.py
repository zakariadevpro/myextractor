"""Seed the database with initial data (plans, admin user)."""

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Adjust import path when running from project root
import sys
sys.path.insert(0, "backend")

from app.config import settings
from app.core.security import hash_password
from app.models.organization import Organization
from app.models.subscription import Plan, Subscription
from app.models.user import User
from app.db.base import Base


PLANS = [
    {
        "name": "Starter",
        "slug": "starter",
        "monthly_price_cents": 2900,
        "max_leads_per_month": 500,
        "max_users": 2,
        "max_extractions_per_day": 5,
    },
    {
        "name": "Pro",
        "slug": "pro",
        "monthly_price_cents": 7900,
        "max_leads_per_month": 2000,
        "max_users": 10,
        "max_extractions_per_day": 20,
    },
    {
        "name": "Enterprise",
        "slug": "enterprise",
        "monthly_price_cents": 19900,
        "max_leads_per_month": 10000,
        "max_users": 50,
        "max_extractions_per_day": 100,
    },
]


async def seed():
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as db:
        # Seed plans
        for plan_data in PLANS:
            existing = await db.execute(select(Plan).where(Plan.slug == plan_data["slug"]))
            if not existing.scalar_one_or_none():
                db.add(Plan(**plan_data))
                print(f"  Created plan: {plan_data['name']}")
            else:
                print(f"  Plan already exists: {plan_data['name']}")

        # Seed default organization + admin
        existing_org = await db.execute(
            select(Organization).where(Organization.slug == "winaity")
        )
        if not existing_org.scalar_one_or_none():
            org = Organization(name="Winaity", slug="winaity")
            db.add(org)
            await db.flush()

            admin = User(
                organization_id=org.id,
                email="admin@winaity.com",
                password_hash=hash_password("admin123"),
                first_name="Admin",
                last_name="Winaity",
                role="super_admin",
            )
            db.add(admin)
            await db.flush()

            # Assign Pro plan
            pro_plan = await db.execute(select(Plan).where(Plan.slug == "pro"))
            pro = pro_plan.scalar_one_or_none()
            if pro:
                sub = Subscription(
                    organization_id=org.id,
                    plan_id=pro.id,
                    status="active",
                )
                db.add(sub)

            print(f"  Created org: Winaity + super admin user (admin@winaity.com / admin123)")
        else:
            print("  Default org already exists")

        await db.commit()

    await engine.dispose()
    print("\nSeed completed!")


if __name__ == "__main__":
    asyncio.run(seed())
