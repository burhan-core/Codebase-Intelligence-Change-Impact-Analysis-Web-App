"""Webhook transport for automated PR analysis.

Signature verification happens over the raw body *before* any JSON parsing:
the endpoint is public, so untrusted input must never reach the parser. The
handler returns 202 immediately and analyzes in the background because GitHub
expects a response within ~10 seconds and retries on timeout — a synchronous
handler would generate duplicate deliveries and duplicate work under exactly
the load you least want that to happen.
"""

import hashlib
import hmac
import os
import traceback
from collections import OrderedDict
from typing import Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from services import github_app, pr_report

router = APIRouter()

RELEVANT_ACTIONS = {"opened", "synchronize", "reopened"}

# Bounded set of processed delivery ids. GitHub guarantees *at least once*
# delivery, so a retry must not analyze twice and post twice. Bounded because
# this is a memory-resident dedupe window, not a durable log.
_SEEN_DELIVERIES: "OrderedDict[str, bool]" = OrderedDict()
_MAX_SEEN = 1000


def verify_signature(secret: str, body: bytes, header: Optional[str]) -> bool:
    """Constant-time HMAC-SHA256 check of `X-Hub-Signature-256`.

    `hmac.compare_digest` rather than `==`: string equality short-circuits on
    the first differing byte, which leaks the signature through timing.
    """
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[len("sha256="):])


def seen_delivery(delivery_id: str) -> bool:
    """Records a delivery id, returning True if it was already processed."""
    if not delivery_id:
        return False
    if delivery_id in _SEEN_DELIVERIES:
        return True
    _SEEN_DELIVERIES[delivery_id] = True
    while len(_SEEN_DELIVERIES) > _MAX_SEEN:
        _SEEN_DELIVERIES.popitem(last=False)
    return False


def handle_pull_request(payload: Dict) -> None:
    """Analyzes a PR and writes the result back. Never raises.

    A failed analysis is reported through a `neutral` check run rather than
    propagated: this tool must not block a merge because a clone timed out.
    """
    repository = payload.get("repository", {})
    repo_full_name = repository.get("full_name", "")
    clone_url = repository.get("clone_url", "")
    pr_number = payload.get("number")
    head_sha = payload.get("pull_request", {}).get("head", {}).get("sha", "")
    installation_id = payload.get("installation", {}).get("id")

    token = None
    try:
        if installation_id is not None:
            token = github_app.installation_token(installation_id)

        impact = pr_report.analyze_pr(
            repo_full_name, pr_number, head_sha, clone_url, token=token
        )
        body = pr_report.render_markdown(impact)

        if token:
            github_app.upsert_comment(repo_full_name, pr_number, body, token)
            github_app.post_check_run(
                repo_full_name,
                head_sha,
                title=f"{len(impact.impacted)} dependent(s) affected",
                summary=body,
                conclusion="success",
                token=token,
            )
    except Exception as exc:
        traceback.print_exc()
        if token and head_sha:
            try:
                github_app.post_check_run(
                    repo_full_name,
                    head_sha,
                    title="Impact analysis could not complete",
                    summary=(
                        "Impact Lens failed to analyze this pull request.\n\n"
                        f"```\n{exc}\n```"
                    ),
                    conclusion="neutral",
                    token=token,
                )
            except Exception:
                traceback.print_exc()


@router.post("/api/github/webhook")
async def github_webhook(request: Request, background: BackgroundTasks):
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="Webhook secret is not configured")

    body = await request.body()
    if not verify_signature(secret, body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status_code=401, detail="Invalid signature")

    delivery_id = request.headers.get("X-GitHub-Delivery", "")
    if seen_delivery(delivery_id):
        return {"status": "duplicate", "delivery": delivery_id}

    event = request.headers.get("X-GitHub-Event", "")
    if event != "pull_request":
        return {"status": "ignored", "event": event}

    payload = await request.json()
    if payload.get("action") not in RELEVANT_ACTIONS:
        return {"status": "ignored", "action": payload.get("action")}

    background.add_task(handle_pull_request, payload)
    return JSONResponse(status_code=202, content={"status": "queued"})


class ManualAnalyzeRequest(BaseModel):
    repo_url: str
    pr_number: int


def _analyze_from_url(repo_url: str, pr_number: int) -> pr_report.PRImpact:
    """Manual entry point: resolves the head SHA from the public API."""
    full_name = repo_url.rstrip("/").removesuffix(".git")
    full_name = "/".join(full_name.split("/")[-2:])

    token = os.environ.get("GITHUB_TOKEN") or None
    details = github_app.pull_request(full_name, pr_number, token)
    head_sha = details["head"]["sha"]
    # Base repo, not head: the head may be a fork, and the head branch is
    # usually deleted once the PR is merged. analyze_pr fetches the commit
    # through refs/pull/<n>/head on the base remote.
    clone_url = details["base"]["repo"]["clone_url"]

    return pr_report.analyze_pr(full_name, pr_number, head_sha, clone_url, token=token)


@router.post("/api/pr/analyze")
def analyze_pr_manually(request: ManualAnalyzeRequest):
    """Same analysis as the webhook, triggered by hand.

    Exists because local development has no publicly reachable URL for GitHub
    to call, and a live demo should not depend on webhook delivery.
    """
    try:
        impact = _analyze_from_url(request.repo_url, request.pr_number)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {
        "repo": impact.repo,
        "pr": impact.pr,
        "head_sha": impact.head_sha,
        "changed_files": impact.changed_files,
        "targets": impact.targets,
        "impacted": impact.impacted,
        "impacted_files": impact.impacted_files,
        "stats": impact.stats,
        "markdown": pr_report.render_markdown(impact),
    }
