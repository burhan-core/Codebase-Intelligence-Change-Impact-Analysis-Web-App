import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from services import pr_webhook

SECRET = "s3cret"


def sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)
    pr_webhook._SEEN_DELIVERIES.clear()

    from main import app

    return TestClient(app)


def _payload(action="opened"):
    return {
        "action": action,
        "number": 7,
        "installation": {"id": 42},
        "pull_request": {"head": {"sha": "abc123"}},
        "repository": {
            "full_name": "owner/repo",
            "clone_url": "https://github.com/owner/repo.git",
        },
    }


def test_verify_signature_accepts_a_correct_signature():
    body = b'{"a":1}'
    assert pr_webhook.verify_signature(SECRET, body, sign(body)) is True


def test_verify_signature_rejects_a_tampered_body():
    assert pr_webhook.verify_signature(SECRET, b'{"a":2}', sign(b'{"a":1}')) is False


def test_verify_signature_rejects_a_wrong_secret():
    body = b'{"a":1}'
    assert pr_webhook.verify_signature(SECRET, body, sign(body, "other")) is False


def test_verify_signature_rejects_a_missing_header():
    assert pr_webhook.verify_signature(SECRET, b'{"a":1}', None) is False


def test_unsigned_request_is_rejected(client):
    response = client.post("/api/github/webhook", json=_payload())
    assert response.status_code == 401


def test_signed_pull_request_event_is_accepted(client, monkeypatch):
    calls = []
    monkeypatch.setattr(pr_webhook, "handle_pull_request", lambda payload: calls.append(payload))

    body = json.dumps(_payload()).encode()
    response = client.post(
        "/api/github/webhook",
        content=body,
        headers={
            "X-Hub-Signature-256": sign(body),
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "d-1",
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 202
    assert len(calls) == 1


def test_duplicate_delivery_is_processed_once(client, monkeypatch):
    calls = []
    monkeypatch.setattr(pr_webhook, "handle_pull_request", lambda payload: calls.append(payload))

    body = json.dumps(_payload()).encode()
    headers = {
        "X-Hub-Signature-256": sign(body),
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": "d-same",
        "Content-Type": "application/json",
    }

    first = client.post("/api/github/webhook", content=body, headers=headers)
    second = client.post("/api/github/webhook", content=body, headers=headers)

    assert first.status_code == 202
    assert second.status_code == 200
    assert len(calls) == 1


def test_irrelevant_action_is_ignored(client, monkeypatch):
    calls = []
    monkeypatch.setattr(pr_webhook, "handle_pull_request", lambda payload: calls.append(payload))

    body = json.dumps(_payload(action="labeled")).encode()
    response = client.post(
        "/api/github/webhook",
        content=body,
        headers={
            "X-Hub-Signature-256": sign(body),
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "d-2",
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 200
    assert calls == []


def test_ping_event_is_acknowledged(client):
    body = json.dumps({"zen": "hello"}).encode()
    response = client.post(
        "/api/github/webhook",
        content=body,
        headers={
            "X-Hub-Signature-256": sign(body),
            "X-GitHub-Event": "ping",
            "X-GitHub-Delivery": "d-3",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200


def test_missing_secret_returns_503(client, monkeypatch):
    monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
    response = client.post("/api/github/webhook", json=_payload())
    assert response.status_code == 503


def test_manual_endpoint_runs_analysis_and_returns_the_report(client, monkeypatch):
    from services import pr_report

    fake = pr_report.PRImpact(
        repo="owner/repo",
        pr=7,
        head_sha="abc",
        targets=["app/store.py::store_it"],
        impacted=[{"id": "app/main.py::handler", "depth": 1, "confidence": "direct"}],
        impacted_files=["app/main.py"],
        stats={
            "cloned": False,
            "cache_hits": 5,
            "cache_misses": 1,
            "cache_hit_ratio": 0.83,
            "files_total": 6,
            "total_ms": 120.0,
        },
    )
    monkeypatch.setattr(pr_webhook, "_analyze_from_url", lambda url, number: fake)

    response = client.post(
        "/api/pr/analyze", json={"repo_url": "https://github.com/owner/repo", "pr_number": 7}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["targets"] == ["app/store.py::store_it"]
    assert "markdown" in data


def test_health_endpoint_still_works(client):
    assert client.get("/").json()["status"] == "ok"
