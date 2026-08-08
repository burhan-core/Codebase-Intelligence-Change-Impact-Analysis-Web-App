"""Replays a fixed corpus of pull requests and reports the speedup.

Three separate comparisons are reported rather than one number, because a
single figure invites "against what?" and a vague answer reads as inflation.
Publishing the stricter figure next to the headline is what makes the
headline credible.
"""

import argparse
import json
import math
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, List

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services import github_app, metrics, parse_cache, pr_report, repo_cache  # noqa: E402

CORPUS_PATH = Path(__file__).resolve().parent / "corpus.json"


def percentile(values: List[float], p: float) -> float:
    """Nearest-rank percentile.

    Percentiles rather than a mean: cold starts and network variance are
    heavy-tailed, so an average is dragged by outliers and describes no run
    that actually happened. p50 is the typical case, p95 the bad day.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    # Nearest rank: ceil(p/100 * n), 1-indexed. `round` would be wrong here —
    # Python rounds halves to even, so round(1.5) is 2 and p50 of two samples
    # would pick the larger one.
    rank = math.ceil(p / 100 * len(ordered))
    index = max(0, min(len(ordered) - 1, rank - 1))
    return ordered[index]


def _reduction(baseline: List[float], improved: List[float]) -> float:
    base = percentile(baseline, 50)
    if base <= 0:
        return 0.0
    return round((base - percentile(improved, 50)) / base * 100, 1)


def summarize(
    cold: List[float], warm: List[float], full: List[float], incremental: List[float]
) -> Dict:
    return {
        "samples": {
            "cold": len(cold),
            "warm": len(warm),
            "full": len(full),
            "incremental": len(incremental),
        },
        "cold_p50_ms": percentile(cold, 50),
        "cold_p95_ms": percentile(cold, 95),
        "warm_p50_ms": percentile(warm, 50),
        "warm_p95_ms": percentile(warm, 95),
        "full_parse_p50_ms": percentile(full, 50),
        "incremental_parse_p50_ms": percentile(incremental, 50),
        "cold_vs_warm_reduction_pct": _reduction(cold, warm),
        "full_vs_incremental_reduction_pct": _reduction(full, incremental),
    }


def render_table(summary: Dict) -> str:
    lines = [
        "| Comparison | Baseline (p50) | Optimized (p50) | Reduction |",
        "|---|---|---|---|",
        f"| Cold vs warm (full analysis) | {summary['cold_p50_ms']:.0f} ms | "
        f"{summary['warm_p50_ms']:.0f} ms | {summary['cold_vs_warm_reduction_pct']}% |",
        f"| Full reparse vs incremental (parse stage, clone held constant) | "
        f"{summary['full_parse_p50_ms']:.0f} ms | "
        f"{summary['incremental_parse_p50_ms']:.0f} ms | "
        f"{summary['full_vs_incremental_reduction_pct']}% |",
        "",
        f"End-to-end warm p95: {summary['warm_p95_ms']:.0f} ms · "
        f"cold p95: {summary['cold_p95_ms']:.0f} ms · "
        f"samples: {summary['samples']}",
    ]
    return "\n".join(lines)


def _last_stage_ms(field: str) -> float:
    """Reads the most recent metrics record's stage duration."""
    if not metrics.METRICS_PATH.exists():
        return 0.0
    last = metrics.METRICS_PATH.read_text(encoding="utf-8").strip().splitlines()[-1]
    return json.loads(last).get(field, 0.0)


JOBS_CACHE_PATH = Path(__file__).resolve().parent / "jobs.cache.json"


def _prefetch(entry: Dict) -> Dict:
    """Fetches a PR's metadata once, up front.

    Deliberately outside the timed region: GitHub API latency is identical in
    the cold and warm arms, so including it would only add variance to both
    and shrink the apparent difference. It also keeps the run inside the
    unauthenticated rate limit, which is 60 requests per hour.
    """
    full_name = "/".join(entry["repo_url"].rstrip("/").removesuffix(".git").split("/")[-2:])
    token = os.environ.get("GITHUB_TOKEN") or None
    details = github_app.pull_request(full_name, entry["pr_number"], token)
    files = github_app.pr_files(full_name, entry["pr_number"], token)
    return {
        "full_name": full_name,
        "pr_number": entry["pr_number"],
        "head_sha": details["head"]["sha"],
        "clone_url": details["base"]["repo"]["clone_url"],
        "files": files,
    }


def load_jobs(corpus: List[Dict], cache_path: Path, refresh: bool = False) -> List[Dict]:
    """Prefetched PR data, cached on disk.

    Re-running the benchmark should not depend on GitHub being reachable or on
    rate limit headroom — the inputs are fixed by definition, so they are
    fetched once and replayed.
    """
    cached: Dict = {}
    if cache_path.exists() and not refresh:
        for job in json.loads(cache_path.read_text(encoding="utf-8")):
            cached[(job["full_name"], job["pr_number"])] = job

    jobs = []
    fetched_any = False
    for entry in corpus:
        full_name = "/".join(
            entry["repo_url"].rstrip("/").removesuffix(".git").split("/")[-2:]
        )
        key = (full_name, entry["pr_number"])
        if key in cached:
            jobs.append(cached[key])
            continue
        print(f"  fetching {full_name}#{entry['pr_number']}", flush=True)
        jobs.append(_prefetch(entry))
        fetched_any = True

    if fetched_any:
        cache_path.write_text(json.dumps(jobs, indent=2), encoding="utf-8")

    return jobs


def _run_once(job: Dict, cold: bool) -> Dict:
    key = repo_cache.project_key(job["full_name"])

    if cold:
        parse_cache.clear(key)
        target = repo_cache.STORAGE_ROOT / key
        if target.exists():
            shutil.rmtree(target, onerror=repo_cache._remove_readonly)

    impact = pr_report.analyze_pr(
        job["full_name"],
        job["pr_number"],
        job["head_sha"],
        job["clone_url"],
        token=None,
        files=job["files"],
    )
    return impact.stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark PR impact analysis")
    parser.add_argument("--repeats", type=int, default=3, help="warm runs per corpus entry")
    parser.add_argument("--corpus", type=Path, default=CORPUS_PATH)
    parser.add_argument("--jobs-cache", type=Path, default=JOBS_CACHE_PATH)
    parser.add_argument(
        "--refresh", action="store_true", help="re-fetch PR data instead of using the cache"
    )
    args = parser.parse_args()

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    cold, warm, full, incremental = [], [], [], []

    print("loading PR metadata (not timed)...", flush=True)
    jobs = load_jobs(corpus, args.jobs_cache, refresh=args.refresh)

    for job in jobs:
        label = f"{job['full_name']}#{job['pr_number']}"
        print(f"cold: {label}", flush=True)
        stats = _run_once(job, cold=True)
        cold.append(stats["total_ms"])
        # The cold run parsed every file, so its parse stage *is* the
        # full-reparse baseline for this repository.
        full.append(_last_stage_ms("parse_ms"))
        print(
            f"      {stats['files_total']} files, "
            f"{stats['total_ms']:.0f} ms total",
            flush=True,
        )

        for _ in range(args.repeats):
            stats = _run_once(job, cold=False)
            warm.append(stats["total_ms"])
            incremental.append(_last_stage_ms("parse_ms"))
        print(
            f"warm: {label} — {stats['cache_hits']}/{stats['files_total']} cached, "
            f"{stats['total_ms']:.0f} ms total",
            flush=True,
        )

    summary = summarize(cold, warm, full, incremental)
    print()
    print(render_table(summary))


if __name__ == "__main__":
    main()
