"""Orchestrates a single pull request analysis.

The graph is rebuilt from cached metadata on every run rather than patched
per changed file. Call resolution in `build_graph_from_metadata` is global:
a function added anywhere can flip call sites in files that did not change,
so per-file patching silently diverges from a full rebuild. Rebuilding is
affordable because the resolver is indexed and the parsing is cached.
See Decision 1 in the design spec.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services import diff_map, github_app, metrics, parse_cache, repo_cache
from services.graph import build_graph_from_metadata

MAX_LISTED_IMPACTS = 25


@dataclass
class PRImpact:
    repo: str
    pr: int
    head_sha: str
    changed_files: List[str] = field(default_factory=list)
    targets: List[str] = field(default_factory=list)
    impacted: List[Dict] = field(default_factory=list)
    impacted_files: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


def analyze_pr(
    repo_full_name: str,
    pr_number: int,
    head_sha: str,
    clone_url: str,
    token: Optional[str] = None,
    files: Optional[List[Dict]] = None,
) -> PRImpact:
    """Computes the blast radius of a pull request."""
    run = metrics.RunMetrics(repo=repo_full_name, pr=pr_number, head_sha=head_sha)

    with run.stage("fetch_files"):
        pr_file_entries = (
            files
            if files is not None
            else github_app.pr_files(repo_full_name, pr_number, token)
        )

    with run.stage("clone"):
        repo_path, was_cloned = repo_cache.ensure_repo(repo_full_name, clone_url, head_sha)

    key = repo_cache.project_key(repo_full_name)

    with run.stage("blobs"):
        blobs = repo_cache.tree_blobs(repo_path)

    with run.stage("parse"):
        cache_stats = parse_cache.sync(key, repo_path, blobs)

    with run.stage("graph"):
        dg = build_graph_from_metadata(parse_cache.metadata_root_for(key))

    with run.stage("impact"):
        changed_files, targets = _resolve_targets(key, pr_file_entries)
        impacted = _union_blast_radius(dg, targets)

    impacted_files = sorted({node.get("file_path") or node["id"] for node in impacted})

    run.set(
        cloned=was_cloned,
        cache_hits=cache_stats.hits,
        cache_misses=cache_stats.misses,
        cache_deleted=cache_stats.deleted,
        files_total=cache_stats.total,
        changed_files=len(changed_files),
        targets=len(targets),
        impacted=len(impacted),
    )
    record = run.write()

    return PRImpact(
        repo=repo_full_name,
        pr=pr_number,
        head_sha=head_sha,
        changed_files=changed_files,
        targets=targets,
        impacted=impacted,
        impacted_files=impacted_files,
        stats={
            "cloned": was_cloned,
            "cache_hits": cache_stats.hits,
            "cache_misses": cache_stats.misses,
            "cache_hit_ratio": round(cache_stats.hit_ratio, 4),
            "files_total": cache_stats.total,
            "total_ms": record["total_ms"],
        },
    )


def _resolve_targets(key: str, pr_file_entries: List[Dict]):
    """Changed Python files, and the node ids to trace impact from.

    A change inside a function targets that function. A change outside any
    function — imports, module constants — targets the file node instead, so
    the change is still traced rather than silently dropped.
    """
    changed_files: List[str] = []
    targets: List[str] = []

    for entry in pr_file_entries:
        filename = (entry.get("filename") or "").replace("\\", "/")
        if not filename.endswith(".py"):
            continue
        if entry.get("status") == "removed":
            # The file is gone from the head tree; its callers still matter,
            # but there is no metadata to map lines against.
            changed_files.append(filename)
            continue

        changed_files.append(filename)

        metadata_file = parse_cache.metadata_root_for(key) / (filename + ".json")
        if not metadata_file.exists():
            continue
        with open(metadata_file, "r", encoding="utf-8") as handle:
            metadata = json.load(handle)

        ranges = diff_map.changed_line_ranges(entry.get("patch"))
        touched = diff_map.touched_functions(metadata, ranges)

        if touched:
            targets.extend(f"{filename}::{name}" for name in touched)
        elif ranges:
            targets.append(filename)

    return changed_files, targets


def _union_blast_radius(dg, targets: List[str]) -> List[Dict]:
    """Merges each target's impact set, keeping the shallowest depth per node."""
    merged: Dict[str, Dict] = {}

    for target in targets:
        for node in dg.get_impact(target) or []:
            existing = merged.get(node["id"])
            if existing is None or node["depth"] < existing["depth"]:
                merged[node["id"]] = node

    return sorted(merged.values(), key=lambda n: (n["depth"], n["id"]))


def render_markdown(impact: PRImpact) -> str:
    """Renders the PR comment body."""
    if not impact.targets:
        return "## Impact Lens\n\nNo Python changes to analyze in this pull request.\n"

    lines = [
        "## Impact Lens",
        "",
        f"**{len(impact.targets)}** changed symbol(s) — "
        f"**{len(impact.impacted)}** dependent(s) across "
        f"**{len(impact.impacted_files)}** file(s).",
        "",
        "### Changed",
        "",
    ]
    lines.extend(f"- `{target}`" for target in impact.targets)

    if impact.impacted:
        lines += [
            "",
            "### Blast radius",
            "",
            "| Depends on your change | Depth | Confidence |",
            "|---|---|---|",
        ]
        for node in impact.impacted[:MAX_LISTED_IMPACTS]:
            lines.append(
                f"| `{node['id']}` | {node['depth']} | {node.get('confidence', 'direct')} |"
            )
        if len(impact.impacted) > MAX_LISTED_IMPACTS:
            lines.append(f"| _…and {len(impact.impacted) - MAX_LISTED_IMPACTS} more_ | | |")
        lines += [
            "",
            "_`possible` means the call was resolved by name and more than one "
            "definition matched._",
        ]
    else:
        lines += ["", "Nothing in the repository depends on the changed symbols."]

    stats = impact.stats
    lines += [
        "",
        f"<sub>Analyzed {stats['files_total']} files in {stats['total_ms']:.0f} ms — "
        f"{stats['cache_hits']} cached, {stats['cache_misses']} parsed"
        f"{'' if stats['cloned'] else ' · clone reused'}.</sub>",
    ]
    return "\n".join(lines)
