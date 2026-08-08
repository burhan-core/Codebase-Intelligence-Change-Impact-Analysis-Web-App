# GitHub App Integration for Automated PR Impact Analysis

**Date:** 2026-08-08
**Status:** Approved, ready for implementation planning

Every design decision below is recorded with the alternatives that were
rejected and what the choice costs. That reasoning is the point of this
document, not a footnote to it — see also the Interview Q&A section at the end.

---

## Problem

Impact Lens today is manual and stateless with respect to repositories. A user
pastes a repo URL; the backend mints a fresh `uuid4()` project id, full-clones
the repo into `storage/<uuid>/`, AST-parses every `.py` file, and builds a
networkx graph held in a module-level `GRAPH_CACHE` dict.

Two consequences:

1. **Nothing is automated.** Impact analysis is something a human must remember
   to run — which means it is not run at the moment it matters, during review.
2. **Nothing is reusable.** Because the project id is random, analyzing the same
   repository twice produces two unrelated projects sharing no state. Reuse is
   impossible *by construction*, not by oversight.

## Goals

- A GitHub App that analyzes a pull request automatically on `opened`,
  `synchronize`, and `reopened`, writing the blast radius back to the PR.
- Repeat analyses of a known repository avoid redundant work: no re-clone, no
  re-parse of unchanged files.
- The speedup is **measured against a stated baseline** and reproducible from a
  committed benchmark — not asserted.
- A companion document explaining what each piece does, why it exists, what was
  rejected, and what to study.

## Non-goals

| Excluded | Why |
|---|---|
| Job queue (Celery/RQ/Redis) | FastAPI `BackgroundTasks` returns the webhook 202 fast enough at this scale. A queue adds a broker, a worker process, and deploy complexity to solve a problem we do not have yet. Revisit when concurrent installs exceed one worker. |
| Incremental graph patching | Incorrect given global name resolution — see "The correctness trap". |
| AI review on every PR | Slow and costs money per event. Behind an env flag, off by default. |
| Non-Python languages | The parser is Python-only; that constraint is unchanged here. |

---

## Decision 1 — The correctness trap: rebuild the graph, don't patch it

### The finding

`build_graph` resolves a call by scanning **every** discovered function for one
whose id ends with `::<name>` (`backend/services/graph.py:232-246`). Resolution
is global, not file-local. One match becomes a `calls` edge; several matches
become `calls_ambiguous` edges to all candidates.

So **editing one file can legitimately change edges in files that did not
change.** Introduce a second function named `save` anywhere in the repository
and every previously unambiguous `save()` call site flips from `calls` to
`calls_ambiguous`.

### Why rebuild

The intuitive optimization — drop the changed file's nodes, re-add them from
fresh metadata, keep the rest — produces a graph that silently diverges from a
full rebuild. In a tool whose entire promise is *"this is what breaks if you
change this"*, silently wrong edges are the worst possible defect. A missing
caller means a reviewer ships a break the tool promised to catch.

### Alternative rejected: patch incrementally anyway

Faster, and it is what most people expect. Rejected because correctness here is
the product. Making it correct would require maintaining a `name -> definition
count` index and invalidating every call site referencing a name whose count
crossed the 1/many boundary — real work, real bug surface, for a stage that is
not the bottleneck once Decision 4 lands.

### Alternative rejected: make resolution file-local first

Scope-correct import resolution would remove the global dependency and make
patching sound. That is a rewrite of the analysis engine, not an integration
feature. It is the right long-term fix and is recorded as future work.

### Cost

Graph reconstruction runs on every analysis. Decision 4 makes that cheap enough
that it is not the dominant term.

---

## Decision 2 — Deterministic project key and clone reuse

Replace the random project id with a deterministic key derived from the
repository full name (`owner/repo`). On a repeat event, the existing clone is
found on disk and updated via `git fetch` + checkout of the PR head SHA rather
than re-cloned.

**Why:** this is the largest single wall-clock win, and it is the change that
makes every other layer possible — with a random id there is nothing to reuse.

**Why hash the name rather than use `owner/repo` directly:** it is filesystem-
safe across platforms, fixed-length (Windows path limits are already a known
pain here — `ingestion.py:43` sets `core.longpaths`), and avoids a path
traversal surface from attacker-influenced repo names.

**Alternative rejected — keep random ids, add a URL→id lookup table:** an extra
mutable mapping to keep consistent, with no benefit over deriving the id.

**Cost:** disk grows with distinct repositories analyzed. Eviction is future
work; note it rather than build an LRU nobody needs yet.

---

## Decision 3 — Content-hash parse cache

Git already computes a blob SHA per file. Cache maps blob SHA → the metadata
JSON already written under `metadata/<key>/`. Unchanged SHA → reuse, never
invoke `ast.parse`. Changed or absent → parse and update. Deleted files have
their metadata and index entry removed.

**Why content hash rather than mtime:** `git fetch` and checkout rewrite mtimes
arbitrarily, so mtime produces both false invalidations and — worse — false
hits. The blob SHA *is* the content identity, computed by git for free.

**Why cache per file rather than per commit:** a per-commit cache has a near-zero
hit rate (every push is a new commit). Per-file hit rate tracks how much of the
repo actually changed, which for a typical PR is ~2%.

**Alternative rejected — cache only the changed files listed by the PR API:**
tempting, but a force-push or a base change makes that list an unreliable
description of the working tree. Hashing what is on disk is self-verifying: it
cannot be wrong about what it is caching.

**Cost:** one `index.json` read/write per analysis and a hash lookup per file —
negligible against AST parsing.

---

## Decision 4 — Resolver indexes

The rebuild's second pass performs two nested scans: each import scans every
file node (`graph.py:192-202`), and each call scans every discovered function
(`graph.py:232-236`). Both become dictionary lookups by prebuilding
`name -> [function_ids]` and `module_path -> file_id`.

**Why:** it turns roughly O(calls × functions) into O(calls). This is what makes
Decision 1 affordable — we can rebuild every time because rebuilding got cheap.

**Why safe:** pure speedup, no intended behavior change, pinned by a golden test
asserting the indexed builder emits a graph identical to the current builder's
for the same metadata. Without that test this is a refactor on trust.

**Alternative rejected — persist the built graph (pickle) and reload:** faster
still, but it reintroduces a staleness question (which metadata version is this
graph from?) and pickle is an unsafe deserialization surface. Rebuilding from
JSON is cheap, verifiable, and has no version-skew failure mode.

---

## Decision 5 — Webhook handling

`POST /api/github/webhook`: verify `X-Hub-Signature-256`, dedupe on
`X-GitHub-Delivery`, dispatch to a `BackgroundTask`, return 202 immediately.

**Why return before analyzing:** GitHub expects a response within ~10 seconds
and retries on timeout. Analysis can take much longer, so a synchronous handler
would produce duplicate deliveries and duplicate work — the failure mode
compounds under exactly the load you least want it to.

**Why HMAC verification before JSON parsing:** the endpoint is public. Anyone can
POST to it. Verifying the signature over the raw body, before deserializing,
means untrusted input never reaches the parser.

**Why `compare_digest` rather than `==`:** string equality short-circuits on the
first differing byte, leaking signature bytes through timing. `hmac.compare_digest`
is constant-time.

**Why dedupe:** GitHub guarantees *at least once*, not exactly once. Without a
delivery-id check, a retried delivery analyzes twice and posts twice.

**Alternative rejected — a GitHub Action instead of an App:** no public endpoint
to host and no App registration, but it pushes work into the user's CI where
there is no shared server-side cache — which is precisely the mechanism this
feature is about. It also requires every repo to commit a workflow file.

**Alternative rejected — polling the GitHub API on a timer:** no public URL
needed, but it burns rate limit, adds latency proportional to poll interval, and
is strictly worse than a push the platform already offers.

---

## Decision 6 — Two entry points onto one function

The webhook and `POST /api/pr/analyze` (taking `{repo_url, pr_number}`) both
call the same `analyze_pr()`.

**Why:** local development has no publicly reachable URL, and a live demo should
not depend on webhook delivery through a tunnel. Because the trigger is separated
from the analysis, the second entry point costs a handful of lines.

**Why this generalizes:** it is the standard shape — thin transport adapters over
one testable core. The end-to-end test drives `analyze_pr()` directly, no HTTP,
no network, no GitHub.

---

## Decision 7 — Upserted comment plus a check run

One comment per PR, edited in place on each push by locating a prior comment
carrying a hidden HTML marker. Plus a check run with the same summary.

**Why upsert:** `synchronize` fires on every push. Appending would bury the
conversation under near-identical bot comments — the classic reason teams mute
bots, which makes the tool worthless regardless of analysis quality.

**Why also a check run:** comments are prose; a check run puts the result in the
PR's status list where reviewers actually look, and can be required later.

**Why `neutral` and never `failure` on analysis errors:** a static-analysis
helper must not block a merge because a clone timed out. Errors are surfaced,
not enforced.

---

## Architecture

```
GitHub ──webhook──▶ POST /api/github/webhook
                      │  verify HMAC → dedupe delivery → return 202
                      ▼
                  BackgroundTask
                      ▼
                  analyze_pr(repo_full_name, pr_number, base_sha, head_sha)
        ┌─────────────┬──────────────┬───────────────┐
        ▼             ▼              ▼               ▼
   repo_cache    parse_cache    build_graph      pr_report
   clone-or-     blob-SHA →     (indexed         changed files →
   fetch,        metadata,      resolver)        changed functions →
   changed       reparse only                    blast radius →
   file list     what moved                      markdown
                                                     │
                                                     ▼
                              github_app: upsert comment + check run
```

Existing `project_id`-keyed endpoints keep working untouched; the GitHub path
supplies a deterministic id where the manual path supplies a random one.

## Components

| Module (`backend/services/`) | Responsibility |
|---|---|
| `github_app.py` | RS256 JWT from the App private key; exchange for an installation token, cached until expiry; REST helpers: list PR files, upsert comment, create/update check run |
| `pr_webhook.py` | Router. Verify signature, dedupe delivery, dispatch background task, return 202 |
| `repo_cache.py` | Deterministic key; clone-or-fetch; checkout head SHA; changed/added/deleted paths via `git diff --name-status base...head` |
| `parse_cache.py` | Blob SHA → metadata JSON; reuse vs reparse per file; maintain `cache/<key>/index.json`; evict deleted files |
| `pr_report.py` | Orchestrate `analyze_pr()`; map changed lines to enclosing functions; union blast radii; render markdown |
| `metrics.py` | Stage timers appended as one JSON object per run to `data/metrics.jsonl` |

Plus `backend/benchmarks/bench_pr.py`, replaying a fixed PR corpus and printing
the comparison table.

**Why six small modules rather than one `github.py`:** each is independently
testable — `parse_cache` needs no GitHub, `github_app` needs no graph. It also
keeps each file small enough to reason about whole.

### Changed lines → changed functions

Parse hunk headers from each file's patch for new-side line ranges, then select
functions whose `lineno..end_lineno` span intersects a changed range — both
fields already produced by the parser (`parser.py:88-89`). Changes outside any
function (imports, module constants) contribute the **file node** instead.

**Why not treat the whole file as changed:** it inflates the blast radius until
the report is noise. Function-level precision is the reason to have an AST at
all.

**Why intersect spans rather than trust the patch's function context header:**
git's `@@ ... @@` context hint is a heuristic based on indentation and is
frequently wrong for decorated or nested definitions. We already have exact
spans.

---

## Error handling

| Condition | Behavior | Why |
|---|---|---|
| Bad/missing signature | 401, body never parsed | Public endpoint; untrusted input must not reach the parser |
| Duplicate delivery id | 200 no-op | At-least-once delivery demands idempotency |
| Clone/fetch failure | Check run, `conclusion: neutral`, error text | The author sees a real message instead of silence |
| Exception in background task | Logged with traceback, same neutral check run | A failed analysis must never block a merge |
| Missing App credentials | 503 from a startup check | Fail clearly at the boundary, not confusingly per-request |

---

## Testing

pytest, no network in the suite.

- **Signature verification** — valid, tampered body, wrong secret, missing header
- **Delivery dedupe** — same id twice performs work once
- **Parse cache** — hit on unchanged blob, miss on changed, eviction on delete, cold start with no index
- **Changed-lines → functions** — inside a function, spanning two, module level, deleted file
- **Golden graph equivalence** — indexed builder output identical to the current builder's over fixture metadata; this is what makes Decision 4 safe
- **End to end** — `analyze_pr` against a real git repo built in a temp dir with two commits, asserting the markdown names the expected impacted functions

**Why a real temp git repo rather than mocking git:** the feature is *about* git
object behavior — blob SHAs, diff ranges, checkout. Mocking it would test the
mock. A two-commit repo in a temp dir is fast and exercises the real thing.

---

## Measurement

Each run appends one record to `data/metrics.jsonl`: per-stage durations, file
counts, cache hits and misses. `bench_pr.py` replays a fixed corpus and reports
three comparisons, so the claim is never ambiguous about its baseline:

1. **Cold vs warm** — no clone, no cache, versus clone present and cache
   populated. The headline figure. Dominated by skipping `git clone`, and this
   is the framing under which a large reduction is expected.
2. **Full reparse vs incremental reparse**, clone held constant — isolates the
   caching work itself. The figure that survives follow-up questions.
3. **End-to-end p50 and p95** over N replays.

The corpus (specific repos and PR numbers) is named in the results table so
anyone can re-run it. The README reports what the measurements actually show.

**Why three numbers rather than one:** a single number invites the question
"against what?" and a vague answer reads as inflation. Three labelled numbers
makes the headline figure credible precisely *because* the stricter figure is
published next to it.

**Why percentiles rather than an average:** cold starts and network variance are
heavy-tailed; a mean is dragged by outliers and describes no actual run. p50 is
the typical experience, p95 the bad day.

### Deployment caveat

Render's free plan has no persistent disk and idles the service down. The cache
is what makes the warm path fast, so a cold start discards it and the deployed
steady state will not match the benchmark steady state. Benchmarks are run
locally; the documentation states this plainly and notes production wants a
persistent volume.

---

## Configuration

Added to `backend/.env.example` and `render.yaml`:

| Variable | Purpose |
|---|---|
| `GITHUB_APP_ID` | App identifier for the JWT `iss` claim |
| `GITHUB_APP_PRIVATE_KEY` | PEM private key for RS256 signing |
| `GITHUB_WEBHOOK_SECRET` | Shared secret for `X-Hub-Signature-256` |
| `PR_AI_REVIEW` | `off` by default; `on` enables LLM review per PR |
| `CACHE_DIR` | Override cache location for a mounted volume |

New dependencies: `PyJWT` with `cryptography` for RS256. GitHub REST calls reuse
`requests`, already present.

**Why a GitHub App rather than a personal access token:** an App gets short-lived
per-installation tokens scoped to the repos that installed it, is revocable by
the installer, is not tied to an individual's account, and carries its own rate
limit. A PAT is a long-lived credential with that user's full access — the wrong
shape for something that acts on other people's repositories.

---

## Documentation

`docs/GITHUB_APP_INTEGRATION.md`, linked from the main README, carrying **all of
the above reasoning** — not just setup steps:

- what each module does and why it exists
- the full lifecycle from webhook delivery to posted comment
- every decision with its rejected alternatives (Decisions 1-7)
- the correctness trap, in full
- registering the App, required permissions and events, every env var
- how to run the benchmark and how to read its table
- the deployment caveat
- the Interview Q&A section below
- **Topics to study**: GitHub App auth (JWT → installation token) vs PATs; HMAC
  signature verification and replay defense; at-least-once delivery and
  idempotency; content-addressed caching and invalidation; why incremental
  computation is hard when name resolution is global; AST static analysis; BFS
  over reversed edges; background tasks vs job queues; benchmarking methodology,
  warm vs cold, percentiles vs means

---

## Interview Q&A

Anticipated questions, with the honest answer.

**"You claim 80% — 80% of what?"**
Wall clock for a full PR analysis, cold versus warm, on a named corpus. Cold
clones and parses everything; warm reuses the clone and reparses only files whose
blob SHA changed. Most of that reduction is skipping the clone. If you hold the
clone constant and measure only the parse layer, the number is the
parse-isolated figure from the results table — both are published, and the
benchmark is committed so you can re-run it.

> Both figures are filled in from the benchmark's actual output once it runs.
> Nothing in this section is quoted as a number until it has been measured.

**"Isn't most of that just not cloning? That's not really your optimization."**
Correct, and that is why the second number exists. The clone saving comes from
making the project id deterministic, which is itself the design change that made
caching possible — with random ids there was nothing to reuse.

**"Why not patch the graph incrementally instead of rebuilding?"**
Because call resolution is global: a name defined anywhere can flip call sites
in files that did not change. Patching only changed files silently diverges from
a full rebuild. I made rebuilding cheap instead, by replacing two nested scans
with dictionary lookups, and pinned it with a golden test proving the fast
builder emits an identical graph.

**"How do you know your optimization didn't change results?"**
Golden test: same metadata in, byte-identical graph out, old builder versus new.

**"What happens if GitHub delivers the same webhook twice?"**
Deduped on `X-GitHub-Delivery`. GitHub guarantees at-least-once, so the handler
has to be idempotent — otherwise a retry doubles the work and posts twice.

**"Your endpoint is public. What stops someone forging a payload?"**
HMAC-SHA256 over the raw body against the shared secret, compared with
`hmac.compare_digest` for constant time, verified before the JSON is parsed.

**"Why not Celery?"**
Nothing in the current load justifies a broker and a worker process. A
`BackgroundTask` returns the 202 inside GitHub's timeout. The line I would cross
is concurrent installations exceeding what one worker absorbs, or needing retries
that survive a restart.

**"Why an App and not a GitHub Action?"**
An Action runs in the user's CI, where there is no shared server-side cache — the
mechanism this whole feature is built on. It also requires every repo to commit a
workflow file.

**"What breaks at scale?"**
Storage grows per repository with no eviction; the graph cache is per-process so
multiple workers each hold their own; and the free-tier host has no persistent
disk, so a cold start discards the cache. All three are known and documented
rather than hidden.

**"What would you do next?"**
Scope-correct import resolution. It would remove the global-resolution problem,
which both improves accuracy and makes genuine incremental graph updates sound.

**"What was hardest?"**
Realizing the obvious optimization was wrong. Discovering that global name
resolution makes per-file patching unsound changed the whole design — I moved
the caching to the layers where it is provably correct instead.
