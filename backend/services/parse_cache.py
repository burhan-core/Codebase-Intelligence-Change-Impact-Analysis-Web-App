"""Content-addressed parse cache.

Maps a file's git blob SHA to its parsed metadata. Unchanged SHA means
unchanged bytes, so the AST work is skipped entirely. A typical pull request
touches a small fraction of a repository, so the hit rate is high — this is
where the incremental-analysis speedup comes from. See Decision 3.
"""

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from services.parser import parse_file

BASE_DIR = Path(__file__).resolve().parent.parent
METADATA_ROOT = Path(os.environ.get("METADATA_DIR", BASE_DIR / "metadata"))
CACHE_ROOT = Path(os.environ.get("CACHE_DIR", BASE_DIR / "cache"))


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    deleted: int = 0

    @property
    def total(self) -> int:
        return self.hits + self.misses

    @property
    def hit_ratio(self) -> float:
        return self.hits / self.total if self.total else 0.0


def metadata_root_for(project_key: str) -> Path:
    return METADATA_ROOT / project_key


def index_path(project_key: str) -> Path:
    return CACHE_ROOT / project_key / "index.json"


def _load_index(project_key: str) -> Dict[str, str]:
    path = index_path(project_key)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        # A corrupt index is a performance problem, not a correctness one:
        # discard it and reparse everything.
        return {}


def _save_index(project_key: str, index: Dict[str, str]) -> None:
    path = index_path(project_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(index, handle, indent=2)


def _metadata_file(project_key: str, relative_path: str) -> Path:
    return metadata_root_for(project_key) / (relative_path + ".json")


def sync(project_key: str, repo_path: Path, blobs: Dict[str, str]) -> CacheStats:
    """Brings metadata in line with `blobs`, parsing only what changed."""
    index = _load_index(project_key)
    stats = CacheStats()
    new_index: Dict[str, str] = {}

    for relative_path, sha in blobs.items():
        target = _metadata_file(project_key, relative_path)

        # The index alone is not trusted: metadata files and index can drift
        # if a run is interrupted, so the file's existence is also checked.
        if index.get(relative_path) == sha and target.exists():
            stats.hits += 1
            new_index[relative_path] = sha
            continue

        source = repo_path / relative_path
        result = parse_file(str(source))
        result["relative_path"] = relative_path

        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)

        stats.misses += 1
        new_index[relative_path] = sha

    for stale_path in set(index) - set(blobs):
        target = _metadata_file(project_key, stale_path)
        if target.exists():
            target.unlink()
        stats.deleted += 1

    _save_index(project_key, new_index)
    return stats


def clear(project_key: str) -> None:
    """Drops all cached state for a project. Used by the benchmark's cold runs."""
    for path in (metadata_root_for(project_key), CACHE_ROOT / project_key):
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
