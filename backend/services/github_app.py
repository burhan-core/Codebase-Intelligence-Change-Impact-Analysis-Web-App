"""GitHub App authentication and the REST calls this integration needs.

A GitHub App is used rather than a personal access token because it gets
short-lived tokens scoped per installation, is revocable by whoever installed
it, is not tied to an individual's account, and carries its own rate limit.
A PAT would be a long-lived credential with one human's full access — the
wrong shape for something acting on other people's repositories.
"""

import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import jwt
import requests

API_ROOT = "https://api.github.com"
TIMEOUT = 30

# Hidden marker used to find our own previous comment so it can be edited
# rather than duplicated. Invisible in rendered markdown.
COMMENT_MARKER = "<!-- impact-lens-report -->"

# installation_id -> (token, expires_at_epoch)
_TOKEN_CACHE: Dict[int, Any] = {}


class GitHubAppError(Exception):
    """Raised for missing credentials or a non-success GitHub API response."""


def _headers(token: Optional[str]) -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _check(response, context: str):
    if response.status_code >= 300:
        raise GitHubAppError(
            f"{context} failed with {response.status_code}: {response.text[:300]}"
        )
    return response.json()


def app_jwt() -> str:
    """A short-lived JWT proving we are the App, signed with its private key.

    This token cannot touch repository data — it is only used to exchange for
    an installation token. GitHub rejects an `exp` more than 10 minutes out,
    and `iat` is backdated 60s to tolerate clock skew.
    """
    app_id = os.environ.get("GITHUB_APP_ID")
    private_key = os.environ.get("GITHUB_APP_PRIVATE_KEY")
    if not app_id or not private_key:
        raise GitHubAppError("GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY must be set")

    # Env vars often carry literal "\n" instead of real newlines.
    private_key = private_key.replace("\\n", "\n")

    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 540, "iss": str(app_id)}
    return jwt.encode(payload, private_key, algorithm="RS256")


def installation_token(installation_id: int) -> str:
    """Exchanges the App JWT for an installation access token, cached."""
    cached = _TOKEN_CACHE.get(installation_id)
    if cached and cached[1] - 60 > time.time():
        return cached[0]

    response = requests.post(
        f"{API_ROOT}/app/installations/{installation_id}/access_tokens",
        headers=_headers(app_jwt()),
        json=None,
        timeout=TIMEOUT,
    )
    data = _check(response, "installation token request")

    expires_at = datetime.strptime(data["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    _TOKEN_CACHE[installation_id] = (data["token"], expires_at.timestamp())
    return data["token"]


def pull_request(repo_full_name: str, pr_number: int, token: Optional[str]) -> Dict:
    response = requests.get(
        f"{API_ROOT}/repos/{repo_full_name}/pulls/{pr_number}",
        headers=_headers(token),
        params=None,
        timeout=TIMEOUT,
    )
    return _check(response, f"fetching PR {repo_full_name}#{pr_number}")


def pr_files(repo_full_name: str, pr_number: int, token: Optional[str]) -> List[Dict]:
    """Every changed file with its patch, following pagination.

    Without pagination a PR touching more than 30 files would be silently
    truncated — and a partial file list means a partial blast radius, which
    is exactly the failure this tool exists to prevent.
    """
    url = f"{API_ROOT}/repos/{repo_full_name}/pulls/{pr_number}/files"
    collected: List[Dict] = []

    while url:
        response = requests.get(
            url, headers=_headers(token), params={"per_page": 100}, timeout=TIMEOUT
        )
        collected.extend(_check(response, "fetching PR files"))
        url = _next_link(response.headers.get("Link"))

    return collected


def _next_link(link_header: Optional[str]) -> Optional[str]:
    if not link_header:
        return None
    for part in link_header.split(","):
        section = part.split(";")
        if len(section) < 2:
            continue
        if 'rel="next"' in section[1].strip():
            return section[0].strip().strip("<>")
    return None


def upsert_comment(repo_full_name: str, pr_number: int, body: str, token: str) -> Dict:
    """Edits our previous report comment if present, otherwise creates one.

    `synchronize` fires on every push, so appending would bury the review
    conversation under near-identical bot comments — the usual reason teams
    mute a bot, which makes the tool worthless however good the analysis is.
    """
    marked = f"{COMMENT_MARKER}\n{body}"

    listing = requests.get(
        f"{API_ROOT}/repos/{repo_full_name}/issues/{pr_number}/comments",
        headers=_headers(token),
        params={"per_page": 100},
        timeout=TIMEOUT,
    )
    comments = _check(listing, "listing PR comments")

    for comment in comments:
        if COMMENT_MARKER in comment.get("body", ""):
            response = requests.patch(
                f"{API_ROOT}/repos/{repo_full_name}/issues/comments/{comment['id']}",
                headers=_headers(token),
                json={"body": marked},
                timeout=TIMEOUT,
            )
            return _check(response, "updating PR comment")

    response = requests.post(
        f"{API_ROOT}/repos/{repo_full_name}/issues/{pr_number}/comments",
        headers=_headers(token),
        json={"body": marked},
        timeout=TIMEOUT,
    )
    return _check(response, "creating PR comment")


def post_check_run(
    repo_full_name: str,
    head_sha: str,
    title: str,
    summary: str,
    conclusion: str,
    token: str,
) -> Dict:
    """Publishes the result to the PR's status list.

    `conclusion` is 'success' or 'neutral' — never 'failure'. A static-analysis
    helper must not block a merge because a clone timed out. Errors are
    surfaced, not enforced.
    """
    response = requests.post(
        f"{API_ROOT}/repos/{repo_full_name}/check-runs",
        headers=_headers(token),
        json={
            "name": "Impact Lens",
            "head_sha": head_sha,
            "status": "completed",
            "conclusion": conclusion,
            "output": {"title": title, "summary": summary[:65000]},
        },
        timeout=TIMEOUT,
    )
    return _check(response, "creating check run")
