# PR analysis benchmark

Replays a fixed corpus of real pull requests through `pr_report.analyze_pr` and
reports how much the clone cache and the parse cache actually save.

```bash
cd backend
./.venv/Scripts/python.exe -m benchmarks.bench_pr --repeats 3
```

PR metadata is fetched once and cached in `jobs.cache.json`, which is committed.
Re-runs therefore need neither network access nor rate-limit headroom — the
inputs are fixed by definition, so they are replayed rather than re-fetched.
Use `--refresh` to re-fetch.

## Results

Measured 2026-08-08 · Windows 11, 24 logical cores, Python 3.14.6, git 2.54.0 ·
3 PRs × 1 cold + 3 warm runs each.

| Comparison | Baseline (p50) | Optimized (p50) | Reduction |
|---|---|---|---|
| Cold vs warm (full analysis) | 5373 ms | 844 ms | 84.3% |
| Full reparse vs incremental (parse stage, clone held constant) | 1255 ms | 14 ms | 98.9% |

End-to-end warm p95: 936 ms · cold p95: 12638 ms.

| PR | Python files | Cold | Warm |
|---|---|---|---|
| encode/httpx#3699 | 60 | 5217 ms | 795 ms |
| pallets/click#3704 | 77 | 5373 ms | 884 ms |
| psf/black#5294 | 341 | 12638 ms | 844 ms |

Note the shape of that last column: warm time is roughly flat across a 5.7×
range in repository size, because a warm run reparses only the files the PR
touched. Cold time, which reparses everything, scales with the repo.

## Why two comparisons and not one headline number

A single speedup figure invites "against what?", and a vague answer reads as
inflation. The two arms isolate different things:

* **Cold vs warm** is the honest end-to-end story, but most of the cold cost is
  the `git clone` — it flatters the parse cache by crediting it with network
  time.
* **Full reparse vs incremental** holds the clone constant and isolates the
  parse stage alone. It is the stricter figure and the one the parse cache
  actually earns.

Publishing the stricter figure next to the headline is what makes the headline
credible.

## Methodology notes

* **Percentiles, not means.** Cold starts and network variance are heavy-tailed;
  an average is dragged by outliers and describes no run that actually happened.
  p50 is the typical case, p95 the bad day.
* **GitHub API calls are outside the timed region.** That latency is identical
  in the cold and warm arms, so including it would add variance to both and
  shrink the apparent difference.
* **Cold means genuinely cold** — the clone directory is deleted and the parse
  cache cleared before each cold run, so the cold arm's parse stage *is* the
  full-reparse baseline for that repository.
* Absolute numbers are machine- and network-dependent. The reductions are the
  portable part; the millisecond figures are not.

## A note on the corpus

The head commits of `encode/httpx#3699` and `psf/black#5294` are reachable from
no branch in their base repositories — the PR branches were deleted after merge.
They resolve only through GitHub's permanent `refs/pull/<n>/head`, which is why
`repo_cache.ensure_repo` fetches that ref. The corpus is not merely illustrative:
two thirds of it fails outright without that fetch.
