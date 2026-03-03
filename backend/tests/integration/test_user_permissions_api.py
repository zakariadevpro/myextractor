import uuid
from datetime import datetime, timezone

import pytest

from app.core.security import create_access_token
from app.models.subscription import Plan, Subscription


def _headers_for_user(user) -> dict[str, str]:
    token = create_access_token(
        {"sub": str(user.id), "org": str(user.organization_id), "role": user.role}
    )
    return {"Authorization": f"Bearer {token}"}


def _headers_for_identity(user_id: str, organization_id: str, role: str) -> dict[str, str]:
    token = create_access_token({"sub": user_id, "org": organization_id, "role": role})
    return {"Authorization": f"Bearer {token}"}


async def _activate_plan_for_org(db_session, org_id: uuid.UUID, *, max_users: int) -> None:
    plan = Plan(
        id=uuid.uuid4(),
        name=f"Plan {max_users}",
        slug=f"perm-plan-{max_users}-{uuid.uuid4().hex[:6]}",
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
async def test_super_admin_can_assign_user_permissions(client, db_session, test_org, test_user):
    test_user.role = "super_admin"
    await db_session.flush()
    await _activate_plan_for_org(db_session, test_org.id, max_users=4)
    super_headers = _headers_for_user(test_user)

    created = await client.post(
        "/api/v1/users",
        headers=super_headers,
        json={
            "email": "perm.target@example.com",
            "first_name": "Perm",
            "last_name": "Target",
            "role": "admin",
        },
    )
    assert created.status_code == 200
    target_id = created.json()["id"]

    updated = await client.put(
        f"/api/v1/users/{target_id}/permissions",
        headers=super_headers,
        json={"grants": ["api_keys.manage"], "revokes": ["access.admin"]},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert "api_keys.manage" in body["grants"]
    assert "access.admin" in body["revokes"]
    assert "access.admin" not in body["effective_permissions"]


@pytest.mark.asyncio
async def test_revoke_access_admin_blocks_admin_endpoints(client, db_session, test_org, test_user):
    test_user.role = "super_admin"
    await db_session.flush()
    await _activate_plan_for_org(db_session, test_org.id, max_users=5)
    super_headers = _headers_for_user(test_user)

    created = await client.post(
        "/api/v1/users",
        headers=super_headers,
        json={
            "email": "revoked.admin@example.com",
            "first_name": "Revoked",
            "last_name": "Admin",
            "role": "admin",
        },
    )
    assert created.status_code == 200
    target = created.json()
    target_id = target["id"]

    revoked = await client.put(
        f"/api/v1/users/{target_id}/permissions",
        headers=super_headers,
        json={"grants": [], "revokes": ["access.admin"]},
    )
    assert revoked.status_code == 200

    result = await client.get(
        "/api/v1/users",
        headers=super_headers,
    )
    assert result.status_code == 200

    target_headers = _headers_for_identity(target_id, str(test_org.id), "admin")
    create_attempt = await client.post(
        "/api/v1/users",
        headers=target_headers,
        json={
            "email": "should.fail@example.com",
            "first_name": "Should",
            "last_name": "Fail",
            "role": "user",
        },
    )
    assert create_attempt.status_code == 403
