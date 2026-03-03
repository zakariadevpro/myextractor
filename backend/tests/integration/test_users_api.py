import uuid
from datetime import datetime, timezone

import pytest

from app.models.subscription import Plan, Subscription


async def _activate_plan_for_org(db_session, org_id: uuid.UUID, *, max_users: int) -> None:
    plan = Plan(
        id=uuid.uuid4(),
        name=f"Plan {max_users}",
        slug=f"plan-{max_users}-{uuid.uuid4().hex[:6]}",
        monthly_price_cents=9900,
        max_leads_per_month=5000,
        max_users=max_users,
        max_extractions_per_day=100,
        is_active=True,
    )
    db_session.add(plan)
    await db_session.flush()

    db_session.add(
        Subscription(
            id=uuid.uuid4(),
            organization_id=org_id,
            plan_id=plan.id,
            status="active",
            current_period_start=datetime.now(timezone.utc),
        )
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_create_user_respects_default_free_user_limit(
    client, test_org, test_user, auth_headers
):
    response = await client.post(
        "/api/v1/users",
        headers=auth_headers,
        json={
            "email": "new.member@example.com",
            "first_name": "New",
            "last_name": "Member",
            "role": "user",
        },
    )
    assert response.status_code == 400
    assert "User limit reached" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_user_normalizes_email_and_accepts_when_plan_has_capacity(
    client, db_session, test_org, test_user, auth_headers
):
    await _activate_plan_for_org(db_session, test_org.id, max_users=3)

    response = await client.post(
        "/api/v1/users",
        headers=auth_headers,
        json={
            "email": "  NEW.Member@Example.COM ",
            "first_name": "New",
            "last_name": "Member",
            "role": "manager",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "new.member@example.com"
    assert body["role"] == "manager"
    assert body["temporary_password"]


@pytest.mark.asyncio
async def test_create_user_rejects_case_insensitive_duplicate_email(
    client, db_session, test_org, test_user, auth_headers
):
    await _activate_plan_for_org(db_session, test_org.id, max_users=4)

    first = await client.post(
        "/api/v1/users",
        headers=auth_headers,
        json={
            "email": "Client.Team@Example.com",
            "first_name": "Client",
            "last_name": "Team",
            "role": "user",
        },
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/v1/users",
        headers=auth_headers,
        json={
            "email": "client.team@example.com",
            "first_name": "Another",
            "last_name": "Person",
            "role": "user",
        },
    )
    assert second.status_code == 400
    assert "Email already registered" in second.json()["detail"]
