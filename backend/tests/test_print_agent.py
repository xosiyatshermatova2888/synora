"""Print agent: a cloud backend can't reach a LAN printer, so AGENT-mode jobs
queue on the server and a script inside the restaurant collects them."""

from __future__ import annotations

import base64
from datetime import timedelta

import pytest

from app.core.permissions import ALL_PERMISSIONS
from app.integrations import escpos
from app.services import print_agent as agent_service
from tests.conftest import auth_headers, owner_headers, waiter_headers


@pytest.fixture
def sent(monkeypatch):
    """The direct-TCP path must never be used for AGENT printers."""
    calls: list = []

    async def fake_send(host, port, data, **_):
        calls.append((host, port, data))

    monkeypatch.setattr(escpos, "send", fake_send)
    return calls


def _printer(client, headers, branch_id, mode="AGENT", role="KITCHEN", host="192.168.1.60"):
    res = client.post(
        "/api/v1/printers",
        headers=headers,
        json={"branch_id": str(branch_id), "role": role, "name": f"{role} printer", "host": host, "mode": mode},
    )
    assert res.status_code == 201, res.text
    return res.json()


def _token(client, headers, branch_id):
    res = client.post(f"/api/v1/printers/agent/token?branch_id={branch_id}", headers=headers)
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


def _queue_test_job(client, headers, printer_id):
    res = client.post(f"/api/v1/printers/{printer_id}/test", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


class TestQueueing:
    def test_agent_mode_job_waits_instead_of_opening_a_socket(self, client, world, sent):
        printer = _printer(client, owner_headers(world), world.branch_a.id)
        assert printer["mode"] == "AGENT"
        job = _queue_test_job(client, owner_headers(world), printer["id"])
        assert job["status"] == "PENDING" and job["attempts"] == 0
        assert sent == []

    def test_direct_mode_still_prints_immediately(self, client, world, sent):
        printer = _printer(client, owner_headers(world), world.branch_a.id, mode="DIRECT")
        job = _queue_test_job(client, owner_headers(world), printer["id"])
        assert job["status"] == "PRINTED" and len(sent) == 1


class TestAgentProtocol:
    def test_poll_delivers_bytes_and_result_completes_job(self, client, world, sent):
        h = owner_headers(world)
        printer = _printer(client, h, world.branch_a.id)
        agent = _token(client, h, world.branch_a.id)
        job = _queue_test_job(client, h, printer["id"])

        polled = client.post("/api/v1/print-agent/poll", headers=agent).json()["jobs"]
        assert [j["id"] for j in polled] == [job["id"]]
        assert (polled[0]["host"], polled[0]["port"]) == ("192.168.1.60", 9100)
        data = base64.b64decode(polled[0]["data_b64"])
        assert data.startswith(b"\x1b@")  # ESC/POS initialise

        res = client.post(f"/api/v1/print-agent/jobs/{job['id']}/result", headers=agent, json={"ok": True})
        assert res.status_code == 204
        jobs = client.get("/api/v1/print-jobs", headers=h).json()
        done = next(j for j in jobs if j["id"] == job["id"])
        assert done["status"] == "PRINTED" and done["printed_at"]
        # Delivered once, not again.
        assert client.post("/api/v1/print-agent/poll", headers=agent).json()["jobs"] == []
        assert sent == []

    def test_job_is_not_redelivered_during_its_lease(self, client, world):
        h = owner_headers(world)
        printer = _printer(client, h, world.branch_a.id)
        agent = _token(client, h, world.branch_a.id)
        _queue_test_job(client, h, printer["id"])
        assert len(client.post("/api/v1/print-agent/poll", headers=agent).json()["jobs"]) == 1
        assert client.post("/api/v1/print-agent/poll", headers=agent).json()["jobs"] == []

    def test_failed_attempts_retry_then_fail_for_good(self, client, world, monkeypatch):
        monkeypatch.setattr(agent_service, "LEASE", timedelta(0))  # retry without waiting
        h = owner_headers(world)
        printer = _printer(client, h, world.branch_a.id)
        agent = _token(client, h, world.branch_a.id)
        job = _queue_test_job(client, h, printer["id"])

        for attempt in range(1, agent_service.MAX_ATTEMPTS + 1):
            polled = client.post("/api/v1/print-agent/poll", headers=agent).json()["jobs"]
            assert [j["id"] for j in polled] == [job["id"]], attempt
            client.post(f"/api/v1/print-agent/jobs/{job['id']}/result", headers=agent,
                        json={"ok": False, "error": "connection refused"})
        final = next(j for j in client.get("/api/v1/print-jobs", headers=h).json() if j["id"] == job["id"])
        assert final["status"] == "FAILED" and "refused" in final["error"]
        assert final["attempts"] == agent_service.MAX_ATTEMPTS
        assert client.post("/api/v1/print-agent/poll", headers=agent).json()["jobs"] == []

    def test_dashboard_retry_requeues_a_failed_agent_job(self, client, world, monkeypatch):
        monkeypatch.setattr(agent_service, "LEASE", timedelta(0))
        h = owner_headers(world)
        printer = _printer(client, h, world.branch_a.id)
        agent = _token(client, h, world.branch_a.id)
        job = _queue_test_job(client, h, printer["id"])
        for _ in range(agent_service.MAX_ATTEMPTS):
            client.post("/api/v1/print-agent/poll", headers=agent)
            client.post(f"/api/v1/print-agent/jobs/{job['id']}/result", headers=agent, json={"ok": False})
        retried = client.post(f"/api/v1/print-jobs/{job['id']}/retry", headers=h).json()
        assert retried["status"] == "PENDING"
        assert [j["id"] for j in client.post("/api/v1/print-agent/poll", headers=agent).json()["jobs"]] == [job["id"]]

    def test_only_agent_mode_printers_are_served(self, client, world, sent):
        h = owner_headers(world)
        agent_printer = _printer(client, h, world.branch_a.id, mode="AGENT", role="KITCHEN")
        direct_printer = _printer(client, h, world.branch_a.id, mode="DIRECT", role="RECEIPT", host="192.168.1.61")
        agent = _token(client, h, world.branch_a.id)
        _queue_test_job(client, h, direct_printer["id"])
        queued = _queue_test_job(client, h, agent_printer["id"])
        assert [j["id"] for j in client.post("/api/v1/print-agent/poll", headers=agent).json()["jobs"]] == [queued["id"]]

    def test_status_reports_online_after_a_poll(self, client, world):
        h = owner_headers(world)
        status = client.get(f"/api/v1/printers/agent?branch_id={world.branch_a.id}", headers=h).json()
        assert status == {"configured": False, "last_seen_at": None, "online": False}
        agent = _token(client, h, world.branch_a.id)
        client.post("/api/v1/print-agent/poll", headers=agent)
        status = client.get(f"/api/v1/printers/agent?branch_id={world.branch_a.id}", headers=h).json()
        assert status["configured"] and status["online"] and status["last_seen_at"]


class TestAgentSecurity:
    def test_missing_or_wrong_token_is_401(self, client):
        assert client.post("/api/v1/print-agent/poll").status_code == 401
        res = client.post("/api/v1/print-agent/poll", headers={"Authorization": "Bearer pa_nope"})
        assert res.status_code == 401

    def test_user_jwt_is_not_an_agent_token(self, client, world):
        assert client.post("/api/v1/print-agent/poll", headers=owner_headers(world)).status_code == 401

    def test_rotating_invalidates_the_old_token(self, client, world):
        h = owner_headers(world)
        old = _token(client, h, world.branch_a.id)
        new = _token(client, h, world.branch_a.id)
        assert client.post("/api/v1/print-agent/poll", headers=old).status_code == 401
        assert client.post("/api/v1/print-agent/poll", headers=new).status_code == 200

    def test_only_admins_manage_the_token(self, client, world):
        res = client.post(f"/api/v1/printers/agent/token?branch_id={world.branch_a.id}", headers=waiter_headers(world))
        assert res.status_code == 403
        res = client.get(f"/api/v1/printers/agent?branch_id={world.branch_a.id}", headers=waiter_headers(world))
        assert res.status_code == 403

    def test_cannot_mint_a_token_for_another_tenants_branch(self, client, world):
        res = client.post(f"/api/v1/printers/agent/token?branch_id={world.branch_b.id}", headers=owner_headers(world))
        assert res.status_code == 404

    def test_agent_cannot_touch_another_tenants_jobs(self, client, world):
        owner_b = auth_headers(world.owner_b.id, world.restaurant_b.id, list(ALL_PERMISSIONS))
        printer_b = _printer(client, owner_b, world.branch_b.id)
        job_b = _queue_test_job(client, owner_b, printer_b["id"])

        agent_a = _token(client, owner_headers(world), world.branch_a.id)
        assert client.post("/api/v1/print-agent/poll", headers=agent_a).json()["jobs"] == []
        res = client.post(f"/api/v1/print-agent/jobs/{job_b['id']}/result", headers=agent_a, json={"ok": True})
        assert res.status_code == 404
        still = next(j for j in client.get("/api/v1/print-jobs", headers=owner_b).json() if j["id"] == job_b["id"])
        assert still["status"] == "PENDING"

    def test_duplicate_result_keeps_the_first_outcome(self, client, world):
        h = owner_headers(world)
        printer = _printer(client, h, world.branch_a.id)
        agent = _token(client, h, world.branch_a.id)
        job = _queue_test_job(client, h, printer["id"])
        client.post("/api/v1/print-agent/poll", headers=agent)
        client.post(f"/api/v1/print-agent/jobs/{job['id']}/result", headers=agent, json={"ok": True})
        client.post(f"/api/v1/print-agent/jobs/{job['id']}/result", headers=agent, json={"ok": False, "error": "late"})
        final = next(j for j in client.get("/api/v1/print-jobs", headers=h).json() if j["id"] == job["id"])
        assert final["status"] == "PRINTED" and final["error"] is None


class TestUsbPrinters:
    """A USB printer has no IP: it is an AGENT printer whose host is the marker "local"."""

    def _create(self, client, headers, branch_id, **extra):
        return client.post("/api/v1/printers", headers=headers,
                           json={"branch_id": str(branch_id), "role": "KITCHEN", "name": "USB printer", **extra})

    def test_agent_printer_can_be_created_without_an_ip(self, client, world):
        for host in (None, "", "usb", "LOCAL"):
            extra = {"mode": "AGENT"} if host is None else {"mode": "AGENT", "host": host}
            res = self._create(client, owner_headers(world), world.branch_a.id, **extra)
            assert res.status_code == 201, (host, res.text)
            assert res.json()["host"] == "local"
            client.delete(f"/api/v1/printers/{res.json()['id']}", headers=owner_headers(world))

    def test_direct_printer_still_needs_a_private_ip(self, client, world):
        h = owner_headers(world)
        for extra in ({"mode": "DIRECT"}, {"mode": "DIRECT", "host": "usb"}, {"mode": "DIRECT", "host": "8.8.8.8"},
                      {"mode": "AGENT", "host": "8.8.8.8"}, {"mode": "AGENT", "host": "not-an-ip"}):
            assert self._create(client, h, world.branch_a.id, **extra).status_code == 422, extra

    def test_switching_a_usb_printer_to_direct_requires_an_ip(self, client, world):
        h = owner_headers(world)
        printer = self._create(client, h, world.branch_a.id, mode="AGENT").json()
        assert client.patch(f"/api/v1/printers/{printer['id']}", headers=h, json={"mode": "DIRECT"}).status_code == 422
        res = client.patch(f"/api/v1/printers/{printer['id']}", headers=h, json={"mode": "DIRECT", "host": "192.168.1.40"})
        assert res.status_code == 200 and res.json()["host"] == "192.168.1.40"

    def test_agent_receives_the_local_marker(self, client, world):
        h = owner_headers(world)
        printer = self._create(client, h, world.branch_a.id, mode="AGENT").json()
        agent = _token(client, h, world.branch_a.id)
        _queue_test_job(client, h, printer["id"])
        job = client.post("/api/v1/print-agent/poll", headers=agent).json()["jobs"][0]
        assert job["host"] == "local" and base64.b64decode(job["data_b64"]).startswith(b"\x1b@")
