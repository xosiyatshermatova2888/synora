"""Tariff plans, trial/grace/read-only lifecycle, feature + branch limits, and
the card-transfer subscription payment flow (request → receipt → approve)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio

from app.core.permissions import ALL_PERMISSIONS
from app.core.plans import (
    GRACE_DAYS,
    TRIAL_DAYS,
    access_state,
    features_of,
    has_feature,
    price_for,
)
from app.services.subscription import _add_months
from tests.conftest import auth_headers, owner_headers, waiter_headers

NOW = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)


def _r(status="ACTIVE", plan="BUSINESS", trial_end=None, period_end=None):
    return SimpleNamespace(
        subscription_status=status, plan=plan, trial_ends_at=trial_end, current_period_end=period_end
    )


# --- pure rules -----------------------------------------------------------------


class TestAccessState:
    def test_no_expiry_is_always_full(self):
        s = access_state(_r(), NOW)
        assert (s.access, s.plan, s.ends_at, s.can_write) == ("FULL", "BUSINESS", None, True)

    def test_trial_shows_pro_and_counts_days(self):
        s = access_state(_r("TRIAL", trial_end=NOW + timedelta(days=TRIAL_DAYS)), NOW)
        assert s.plan == "PRO" and s.access == "FULL" and s.days_left == TRIAL_DAYS + 1

    def test_last_hours_still_count_as_a_day(self):
        s = access_state(_r("TRIAL", trial_end=NOW + timedelta(hours=3)), NOW)
        assert s.access == "FULL" and s.days_left == 1

    def test_just_expired_enters_grace_with_full_write(self):
        s = access_state(_r(period_end=NOW - timedelta(hours=1)), NOW)
        assert s.access == "GRACE" and s.can_write and s.grace_days_left == GRACE_DAYS

    def test_grace_ends_into_read_only(self):
        inside = access_state(_r(period_end=NOW - timedelta(days=GRACE_DAYS - 1)), NOW)
        outside = access_state(_r(period_end=NOW - timedelta(days=GRACE_DAYS, hours=1)), NOW)
        assert inside.access == "GRACE"
        assert outside.access == "READ_ONLY" and not outside.can_write

    def test_expired_trial_loses_pro_features_after_grace_but_state_is_trial(self):
        s = access_state(_r("TRIAL", trial_end=NOW - timedelta(days=30)), NOW)
        assert s.status == "TRIAL" and s.access == "READ_ONLY"

    def test_naive_datetimes_are_treated_as_utc(self):
        s = access_state(_r(period_end=(NOW - timedelta(days=30)).replace(tzinfo=None)), NOW)
        assert s.access == "READ_ONLY"


class TestCatalog:
    def test_feature_matrix(self):
        assert not has_feature("BUSINESS", "inventory")
        assert has_feature("PRO", "inventory") and has_feature("PRO", "crm")
        assert not has_feature("PRO", "ai_assistant")
        assert has_feature("AI_PREMIUM", "ai_assistant") and has_feature("ENTERPRISE", "ai_assistant")
        assert features_of("BUSINESS") == []

    def test_annual_is_ten_months(self):
        assert price_for("PRO", "MONTHLY") == 499_000
        assert price_for("PRO", "ANNUAL") == 4_990_000

    def test_month_arithmetic_clamps_day(self):
        jan31 = datetime(2027, 1, 31, tzinfo=timezone.utc)
        assert _add_months(jan31, 1) == datetime(2027, 2, 28, tzinfo=timezone.utc)
        assert _add_months(datetime(2026, 12, 15, tzinfo=timezone.utc), 1).year == 2027
        assert _add_months(jan31, 12) == datetime(2028, 1, 31, tzinfo=timezone.utc)


# --- HTTP behaviour ---------------------------------------------------------------


@pytest_asyncio.fixture
async def admin(world, db):
    """beta's owner doubles as the SYNORA platform admin."""
    world.owner_b.is_platform_admin = True
    await db.commit()
    return auth_headers(world.owner_b.id, world.restaurant_b.id, list(ALL_PERMISSIONS))


def _set(client, admin, world, **body):
    res = client.patch(
        f"/api/v1/platform/restaurants/{world.restaurant_a.id}/subscription", headers=admin, json=body
    )
    assert res.status_code == 200, res.text
    return res.json()


def _utc(iso):
    """SQLite hands back naive datetimes; Postgres aware ones. Normalise."""
    moment = datetime.fromisoformat(iso)
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _past(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _future(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


class TestRegistration:
    def test_new_restaurant_gets_a_14_day_pro_trial(self, client):
        res = client.post(
            "/api/v1/auth/register",
            json={
                "restaurant_name": "Trial Diner", "username": "trial_owner",
                "password": "TestPass123!", "full_name": "T Owner",
            },
        )
        assert res.status_code == 201, res.text
        headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
        sub = client.get("/api/v1/subscription", headers=headers).json()
        assert sub["status"] == "TRIAL" and sub["plan"] == "PRO" and sub["access"] == "FULL"
        assert TRIAL_DAYS <= sub["days_left"] <= TRIAL_DAYS + 1
        assert client.get("/api/v1/inventory-items", headers=headers).status_code == 200


class TestFeatureGates:
    def test_business_is_blocked_from_pro_features(self, client, world, admin):
        _set(client, admin, world, plan="BUSINESS", status="ACTIVE", clear_period_end=True)
        h = owner_headers(world)
        for path in ("/api/v1/inventory-items", "/api/v1/customers", "/api/v1/reports/waiters",
                     "/api/v1/reports/expenses", "/api/v1/reports/profit"):
            res = client.get(path, headers=h)
            assert res.status_code == 402, (path, res.text)
            detail = res.json()["detail"]
            assert detail["code"] == "plan_upgrade_required" and detail["required_plan"] == "PRO"
        # Basic reports and POS stay open on Business.
        assert client.get("/api/v1/reports/sales", headers=h).status_code == 200
        assert client.get("/api/v1/reports/products", headers=h).status_code == 200

    def test_pro_unlocks_them(self, client, world, admin):
        _set(client, admin, world, plan="PRO", status="ACTIVE", clear_period_end=True)
        h = owner_headers(world)
        for path in ("/api/v1/inventory-items", "/api/v1/customers", "/api/v1/reports/waiters"):
            assert client.get(path, headers=h).status_code == 200, path

    def test_branch_limits_per_plan(self, client, world, admin):
        h = owner_headers(world)
        body = lambda n: {"name": f"B{n}"}  # noqa: E731
        _set(client, admin, world, plan="BUSINESS", status="ACTIVE", clear_period_end=True)
        res = client.post("/api/v1/branches", headers=h, json=body(1))  # alpha already has Main Branch
        assert res.status_code == 402 and res.json()["detail"]["branch_limit"] == 1

        _set(client, admin, world, plan="PRO")
        assert client.post("/api/v1/branches", headers=h, json=body(2)).status_code == 201
        assert client.post("/api/v1/branches", headers=h, json=body(3)).status_code == 201
        res = client.post("/api/v1/branches", headers=h, json=body(4))  # 4th > cap of 3
        assert res.status_code == 402

        _set(client, admin, world, plan="ENTERPRISE")
        assert client.post("/api/v1/branches", headers=h, json=body(4)).status_code == 201


class TestReadOnlyLifecycle:
    def test_grace_still_writes_but_read_only_blocks(self, client, world, admin):
        h = owner_headers(world)
        category = {"name": "Desserts"}

        _set(client, admin, world, status="ACTIVE", period_end=_past(2))
        assert client.get("/api/v1/subscription", headers=h).json()["access"] == "GRACE"
        assert client.post("/api/v1/menu/categories", headers=h, json=category).status_code == 201

        _set(client, admin, world, period_end=_past(GRACE_DAYS + 2))
        sub = client.get("/api/v1/subscription", headers=h).json()
        assert sub["access"] == "READ_ONLY" and sub["can_write"] is False

        res = client.post("/api/v1/menu/categories", headers=h, json={"name": "Soups"})
        assert res.status_code == 402 and res.json()["detail"]["code"] == "subscription_expired"
        assert client.get("/api/v1/menu/categories", headers=h).status_code == 200  # reading is fine
        assert client.get("/api/v1/orders", headers=h).status_code == 200

    def test_read_only_still_allows_paying_and_auth(self, client, world, admin):
        _set(client, admin, world, status="ACTIVE", period_end=_past(GRACE_DAYS + 5))
        h = owner_headers(world)
        res = client.post(
            "/api/v1/subscription/payments", headers=h, json={"plan": "BUSINESS", "billing_cycle": "MONTHLY"}
        )
        assert res.status_code == 201, res.text

    def test_read_only_blocks_new_orders_from_every_channel(self, client, world, admin):
        _set(client, admin, world, status="ACTIVE", period_end=_past(GRACE_DAYS + 5))
        order = {
            "branch_id": str(world.branch_a.id),
            "table_id": str(world.table_a.id),
            "source": "WAITER",
            "items": [{"product_id": str(world.product_a.id), "quantity": 1,
                       "modifiers": [{"modifier_id": str(world.large_mod.id), "quantity": 1}]}],
        }
        assert client.post("/api/v1/orders", headers=waiter_headers(world), json=order).status_code == 402


class TestPaymentFlow:
    def _request(self, client, world, plan="PRO", cycle="MONTHLY"):
        res = client.post(
            "/api/v1/subscription/payments", headers=owner_headers(world),
            json={"plan": plan, "billing_cycle": cycle},
        )
        assert res.status_code == 201, res.text
        return res.json()

    def test_request_receipt_approve_activates_plan(self, client, world, admin):
        _set(client, admin, world, plan="BUSINESS", status="ACTIVE", clear_period_end=True)
        h = owner_headers(world)
        pay = self._request(client, world, "PRO", "MONTHLY")
        assert pay["status"] == "PENDING" and float(pay["amount"]) == 499_000

        # Only one open request at a time.
        dup = client.post("/api/v1/subscription/payments", headers=h,
                          json={"plan": "PRO", "billing_cycle": "MONTHLY"})
        assert dup.status_code == 409

        res = client.post(f"/api/v1/subscription/payments/{pay['id']}/receipt", headers=h,
                          json={"receipt_url": "/uploads/chek.jpg"})
        assert res.status_code == 200 and res.json()["receipt_url"] == "/uploads/chek.jpg"

        pending = client.get("/api/v1/platform/payments?status=PENDING", headers=admin).json()
        assert [p["id"] for p in pending] == [pay["id"]]
        assert pending[0]["restaurant_name"] == "Alpha Grill"

        ok = client.post(f"/api/v1/platform/payments/{pay['id']}/approve", headers=admin)
        assert ok.status_code == 200 and ok.json()["status"] == "APPROVED"

        sub = client.get("/api/v1/subscription", headers=h).json()
        assert sub["plan"] == "PRO" and sub["status"] == "ACTIVE" and sub["access"] == "FULL"
        assert 29 <= sub["days_left"] <= 32
        assert client.get("/api/v1/inventory-items", headers=h).status_code == 200

    def test_double_approve_does_not_extend_twice(self, client, world, admin):
        pay = self._request(client, world, "PRO", "MONTHLY")
        first = client.post(f"/api/v1/platform/payments/{pay['id']}/approve", headers=admin).json()
        second = client.post(f"/api/v1/platform/payments/{pay['id']}/approve", headers=admin).json()
        assert first["period_end"] == second["period_end"]

    def test_early_renewal_stacks_on_remaining_time(self, client, world, admin):
        _set(client, admin, world, plan="PRO", status="ACTIVE", period_end=_future(10))
        pay = self._request(client, world, "PRO", "MONTHLY")
        done = client.post(f"/api/v1/platform/payments/{pay['id']}/approve", headers=admin).json()
        start = _utc(done["period_start"])
        assert 9 <= (start - datetime.now(timezone.utc)).days <= 10
        assert (_utc(done["period_end"]) - start).days in (28, 29, 30, 31)

    def test_paying_from_read_only_restores_writes(self, client, world, admin):
        _set(client, admin, world, status="ACTIVE", period_end=_past(GRACE_DAYS + 3))
        h = owner_headers(world)
        assert client.post("/api/v1/menu/categories", headers=h, json={"name": "X"}).status_code == 402
        pay = self._request(client, world, "BUSINESS", "ANNUAL")
        client.post(f"/api/v1/platform/payments/{pay['id']}/approve", headers=admin)
        assert client.post("/api/v1/menu/categories", headers=h, json={"name": "X"}).status_code == 201

    def test_reject_keeps_plan_and_allows_new_request(self, client, world, admin):
        _set(client, admin, world, plan="BUSINESS", status="ACTIVE", clear_period_end=True)
        pay = self._request(client, world)
        res = client.post(f"/api/v1/platform/payments/{pay['id']}/reject", headers=admin,
                          json={"reason": "Chek ko'rinmadi"})
        assert res.status_code == 200 and res.json()["status"] == "REJECTED"
        assert client.get("/api/v1/subscription", headers=owner_headers(world)).json()["plan"] == "BUSINESS"
        # A rejected payment can't be approved later; a fresh request is allowed.
        assert client.post(f"/api/v1/platform/payments/{pay['id']}/approve", headers=admin).status_code == 422
        self._request(client, world)

    @pytest.mark.parametrize(
        "url",
        ["javascript:alert(document.cookie)", "https://evil.example/phish.png", "//evil.example/x.png",
         "/uploads/../../etc/passwd", "data:text/html,<script>1</script>"],
    )
    def test_receipt_must_be_one_of_our_own_uploads(self, client, world, url):
        pay = self._request(client, world)
        res = client.post(f"/api/v1/subscription/payments/{pay['id']}/receipt",
                          headers=owner_headers(world), json={"receipt_url": url})
        assert res.status_code == 400, url

    def test_enterprise_is_not_payable_by_card(self, client, world):
        res = client.post("/api/v1/subscription/payments", headers=owner_headers(world),
                          json={"plan": "ENTERPRISE", "billing_cycle": "MONTHLY"})
        assert res.status_code == 400

    def test_payment_amounts_are_server_side(self, client, world):
        res = client.post("/api/v1/subscription/payments", headers=owner_headers(world),
                          json={"plan": "BUSINESS", "billing_cycle": "ANNUAL", "amount": 1})
        assert float(res.json()["amount"]) == 2_990_000


class TestAccessControl:
    def test_tenant_staff_cannot_use_platform_endpoints(self, client, world):
        h = owner_headers(world)
        assert client.get("/api/v1/platform/restaurants", headers=h).status_code == 403
        assert client.get("/api/v1/platform/payments", headers=h).status_code == 403
        assert client.post(f"/api/v1/platform/payments/{world.restaurant_a.id}/approve", headers=h).status_code == 403

    def test_waiter_can_read_state_but_not_pay_or_see_catalog(self, client, world):
        h = waiter_headers(world)
        assert client.get("/api/v1/subscription", headers=h).status_code == 200
        assert client.get("/api/v1/subscription/plans", headers=h).status_code == 403
        assert client.get("/api/v1/subscription/payments", headers=h).status_code == 403
        assert client.post("/api/v1/subscription/payments", headers=h,
                           json={"plan": "PRO", "billing_cycle": "MONTHLY"}).status_code == 403

    def test_payments_are_tenant_isolated(self, client, world, admin):
        pay = client.post("/api/v1/subscription/payments", headers=owner_headers(world),
                          json={"plan": "PRO", "billing_cycle": "MONTHLY"}).json()
        other = auth_headers(world.owner_b.id, world.restaurant_b.id, list(ALL_PERMISSIONS))
        assert client.get("/api/v1/subscription/payments", headers=other).json() == []
        # Another tenant can't attach a receipt to it either (404, not 403).
        res = client.post(f"/api/v1/subscription/payments/{pay['id']}/receipt", headers=other,
                          json={"receipt_url": "/uploads/synora-uploads/x.jpg"})
        assert res.status_code == 404

    def test_me_reports_platform_admin_flag(self, client, world, admin):
        assert client.get("/api/v1/auth/me", headers=admin).json()["is_platform_admin"] is True
        assert client.get("/api/v1/auth/me", headers=owner_headers(world)).json()["is_platform_admin"] is False
