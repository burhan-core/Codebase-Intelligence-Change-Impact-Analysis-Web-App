"""Deterministic, reusable clones keyed by repository identity.

The original ingestion path minted a `uuid4()` per clone, which made reuse
impossible by construction: the same repository analyzed twice produced two
unrelated projects. Keying by `owner/repo` is what turns a second analysis
into a fetch instead of a clone. See Decision 2 in the design spec.
"""

import hashlib
import os
import shutil
import stat
from pathlib import Path
from typing import Dict, Optional, Tuple

import git

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_ROOT = Path(os.environ.get("CACHE_DIR", BASE_DIR / "storage"))


class RepoCacheError(Exception):
    """Raised when a repository cannot be cloned, fetched, or checked out."""


def _remove_readonly(func, path, _excinfo):
    """Windows leaves .git objects read-only; clear the bit and retry."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def project_key(repo_full_name: str) -> str:
    """A stable, filesystem-safe id for a repository.

    Hashed rather than used literally: fixed length (Windows path limits are
    already a known pain here), no separators to escape, and no path-traversal
    surface from an attacker-influenced repository name.
    """
    normalized = repo_full_name.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _git_env() -> Dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"  # never block waiting for credentials
    return env


def ensure_repo(
    repo_full_name: str,
    clone_url: str,
    ref: str,
    fetch_ref: Optional[str] = None,
) -> Tuple[Path, bool]:
    """Ensures a clone exists at `ref`. Returns (path, was_cloned).

    `fetch_ref` is fetched before checkout, and for GitHub pull requests it
    must be `refs/pull/<n>/head`. A PR head commit is frequently *not*
    reachable from any branch in the base repository: the head branch is
    deleted after merge, and a fork's commits were never in the base repo at
    all. GitHub keeps `refs/pull/<n>/head` permanently, so it is the only
    reliable way to obtain the commit — and it works identically for forks.

    The fetch is best-effort: a remote without that ref (a plain git URL, a
    test fixture) falls through to a normal fetch and checkout.
    """
    target = STORAGE_ROOT / project_key(repo_full_name)
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

    was_cloned = False
    if not (target / ".git").exists():
        if target.exists():
            shutil.rmtree(target, onerror=_remove_readonly)
        try:
            git.Repo.clone_from(
                clone_url,
                target,
                env=_git_env(),
                multi_options=["-c core.longpaths=true"],
                allow_unsafe_options=True,
            )
        except Exception as exc:
            if target.exists():
                shutil.rmtree(target, onerror=_remove_readonly)
            raise RepoCacheError(f"Failed to clone {repo_full_name}: {exc}") from exc
        was_cloned = True

    try:
        repo = git.Repo(target)
        with repo.git.custom_environment(**_git_env()):
            fetched_pull_ref = False
            if fetch_ref:
                try:
                    repo.git.fetch("origin", "--force", fetch_ref)
                    fetched_pull_ref = True
                except Exception:
                    # Remote has no such ref (plain git URL, test fixture).
                    # Fall through to the ordinary refs.
                    pass
            if not fetched_pull_ref and not was_cloned:
                repo.git.fetch("origin", "--prune", "--tags", "--force")
            repo.git.checkout(ref, force=True)
    except Exception as exc:
        raise RepoCacheError(
            f"Failed to check out {ref} for {repo_full_name}: {exc}"
        ) from exc

    return target, was_cloned


def tree_blobs(repo_path: Path) -> Dict[str, str]:
    """Maps every tracked `.py` path to its git blob SHA.

    The blob SHA *is* the content identity, computed by git for free. mtime
    would be wrong here: fetch and checkout rewrite mtimes arbitrarily,
    producing both false invalidations and false cache hits.
    """
    repo = git.Repo(repo_path)
    listing = repo.git.ls_tree("-r", "HEAD")

    blobs: Dict[str, str] = {}
    for line in listing.splitlines():
        if not line.strip():
            continue
        # Format: "<mode> <type> <sha>\t<path>"
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) != 3:
            continue
        _mode, obj_type, sha = parts
        if obj_type != "blob" or not path.endswith(".py"):
            continue
        blobs[path.replace("\\", "/")] = sha
    return blobs
