import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from services import github_app


@pytest.fixture
def app_credentials(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    monkeypatch.setenv("GITHUB_APP_ID", "12345")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", pem)
    github_app._TOKEN_CACHE.clear()
    return {"pem": pem, "public": key.public_key()}


class FakeResponse:
    def __init__(self, payload, status=200, headers=None):
        self._payload = payload
        self.status_code = status
        self.headers = headers or {}
        self.text = str(payload)

    def json(self):
        return self._payload


def test_app_jwt_is_signed_rs256_with_expected_claims(app_credentials):
    token = github_app.app_jwt()
    claims = jwt.decode(token, app_credentials["public"], algorithms=["RS256"])

    assert claims["iss"] == "12345"
    assert claims["exp"] - claims["iat"] <= 600
    assert claims["iat"] <= int(time.time())


def test_app_jwt_without_credentials_raises(monkeypatch):
    monkeypatch.delenv("GITHUB_APP_ID", raising=False)
    monkeypatch.delenv("GITHUB_APP_PRIVATE_KEY", raising=False)
    with pytest.raises(github_app.GitHubAppError):
        github_app.app_jwt()


def test_installation_token_is_cached_until_near_expiry(app_credentials, monkeypatch):
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(url)
        expires = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 3600))
        return FakeResponse({"token": "ghs_abc", "expires_at": expires}, status=201)

    monkeypatch.setattr(github_app.requests, "post", fake_post)

    assert github_app.installation_token(99) == "ghs_abc"
    assert github_app.installation_token(99) == "ghs_abc"
    assert len(calls) == 1


def test_installation_token_refetches_when_expired(app_credentials, monkeypatch):
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(url)
        expires = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 10))
        return FakeResponse({"token": "ghs_old", "expires_at": expires}, status=201)

    monkeypatch.setattr(github_app.requests, "post", fake_post)

    github_app.installation_token(99)
    github_app.installation_token(99)
    assert len(calls) == 2


def test_pr_files_follows_pagination(monkeypatch):
    pages = [
        FakeResponse([{"filename": "a.py"}], headers={"Link": '<https://x/page2>; rel="next"'}),
        FakeResponse([{"filename": "b.py"}]),
    ]

    def fake_get(url, headers=None, params=None, timeout=None):
        return pages.pop(0)

    monkeypatch.setattr(github_app.requests, "get", fake_get)

    files = github_app.pr_files("o/r", 1, token=None)
    assert [f["filename"] for f in files] == ["a.py", "b.py"]


def test_upsert_comment_edits_an_existing_marked_comment(monkeypatch):
    existing = [
        {"id": 1, "body": "unrelated human comment"},
        {"id": 2, "body": f"{github_app.COMMENT_MARKER}\nold report"},
    ]
    patched = {}

    def fake_get(url, headers=None, params=None, timeout=None):
        return FakeResponse(existing)

    def fake_patch(url, headers=None, json=None, timeout=None):
        patched["url"] = url
        patched["body"] = json["body"]
        return FakeResponse({"id": 2})

    def fake_post(url, headers=None, json=None, timeout=None):
        raise AssertionError("should not create a new comment when one exists")

    monkeypatch.setattr(github_app.requests, "get", fake_get)
    monkeypatch.setattr(github_app.requests, "patch", fake_patch)
    monkeypatch.setattr(github_app.requests, "post", fake_post)

    github_app.upsert_comment("o/r", 1, "new report", token="t")

    assert patched["url"].endswith("/issues/comments/2")
    assert github_app.COMMENT_MARKER in patched["body"]
    assert "new report" in patched["body"]


def test_upsert_comment_creates_when_none_exists(monkeypatch):
    created = {}

    monkeypatch.setattr(github_app.requests, "get", lambda *a, **k: FakeResponse([]))

    def fake_post(url, headers=None, json=None, timeout=None):
        created["url"] = url
        created["body"] = json["body"]
        return FakeResponse({"id": 3}, status=201)

    monkeypatch.setattr(github_app.requests, "post", fake_post)

    github_app.upsert_comment("o/r", 1, "first report", token="t")

    assert created["url"].endswith("/issues/1/comments")
    assert github_app.COMMENT_MARKER in created["body"]


def test_api_error_raises_github_app_error(monkeypatch):
    monkeypatch.setattr(
        github_app.requests,
        "get",
        lambda *a, **k: FakeResponse({"message": "Not Found"}, status=404),
    )
    with pytest.raises(github_app.GitHubAppError):
        github_app.pull_request("o/r", 1, token=None)
