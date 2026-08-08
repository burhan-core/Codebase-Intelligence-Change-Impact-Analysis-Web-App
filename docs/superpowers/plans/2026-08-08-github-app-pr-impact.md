# GitHub App PR Impact Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A GitHub App that automatically analyzes every pull request's blast radius and posts it back to the PR, with a three-layer cache making repeat analyses substantially faster.

**Architecture:** A webhook endpoint verifies GitHub's HMAC signature, dedupes the delivery, and hands off to a background task that calls one `analyze_pr()` function. That function reuses an on-disk clone keyed deterministically by repo name, re-parses only files whose git blob SHA changed, rebuilds the dependency graph from cached metadata using dictionary-based resolver indexes, and renders a markdown report posted as an upserted PR comment plus a check run.

**Tech Stack:** Python 3.12, FastAPI, GitPython, networkx, PyJWT + cryptography (RS256 App auth), requests, pytest.

**Spec:** `docs/superpowers/specs/2026-08-08-github-app-pr-impact-design.md`. Read it before starting — especially "The correctness trap" (Decision 1), which explains why the graph is rebuilt rather than patched.

## Global Constraints

- All new backend modules live in `backend/services/`. All tests live in `backend/tests/`.
- **No network access in the test suite.** GitHub HTTP calls are monkeypatched; git operations use real repositories built in `tmp_path`.
- Run all commands from the `backend/` directory unless stated otherwise. Tests are run with `python -m pytest` so the venv's interpreter resolves `services.*` imports.
- Path separators in graph node ids and cache keys are always forward slashes. The existing builder normalizes with `.replace("\\", "/")` (`services/graph.py:143`); preserve that.
- Never log or echo `GITHUB_APP_PRIVATE_KEY` or `GITHUB_WEBHOOK_SECRET`.
- Existing `project_id`-keyed endpoints in `main.py` must keep working unchanged. Verify after each task that `GET /` still returns `{"status": "ok"}`.
- Commit after every task. Do not batch commits across tasks.

## Deviation from the spec (approved)

The spec's Decision 2 lists `git diff --name-status base...head` as the source of changed files. A `depth=1` clone has no merge base, so that command fails or returns garbage against exactly the clones we create. Instead:

- **Changed files and their patches** come from the GitHub PR files API (`GET /repos/{repo}/pulls/{n}/files`), which we already call and which returns the hunk data we need for line ranges anyway.
- **Blob SHAs for the parse cache** come from `git ls-tree -r HEAD`, i.e. hashing what is actually on disk.

This is *more* faithful to Decision 3, which explicitly rejected trusting the PR file list as the cache's source of truth on the grounds that a force-push makes it unreliable. The two sources now serve their appropriate purposes: the API says *what the human changed*, git says *what the tree contains*.

## File Structure

**Created:**

| Path | Responsibility |
|---|---|
| `backend/tests/conftest.py` | Shared fixtures: temp git repos, fake metadata trees |
| `backend/tests/test_*.py` | One test module per service module |
| `backend/requirements-dev.txt` | Test-only dependencies |
| `backend/services/metrics.py` | Stage timing, one JSONL record per run |
| `backend/services/repo_cache.py` | Deterministic project key, clone-or-fetch, blob SHA listing |
| `backend/services/parse_cache.py` | Blob SHA → metadata JSON; reuse vs reparse |
| `backend/services/diff_map.py` | Patch hunk ranges → touched function names |
| `backend/services/github_app.py` | App JWT, installation tokens, GitHub REST helpers |
| `backend/services/pr_report.py` | `analyze_pr()` orchestration + markdown rendering |
| `backend/services/pr_webhook.py` | Webhook router: signature, dedupe, dispatch |
| `backend/benchmarks/bench_pr.py` | Replays a PR corpus, prints the comparison table |
| `docs/GITHUB_APP_INTEGRATION.md` | The explanatory document |

**Modified:**

| Path | Change |
|---|---|
| `backend/services/graph.py` | Split `build_graph` into a metadata-path variant; add resolver indexes |
| `backend/main.py` | Mount the webhook router and the manual analyze endpoint |
| `backend/requirements.txt` | Add PyJWT, cryptography |
| `backend/.env.example`, `render.yaml` | New environment variables |
| `.gitignore` | Ignore `backend/cache/`, `backend/data/` |
| `README.md` | Link the new doc |

`diff_map.py` is split out of `pr_report.py` (which the spec listed as owning it) because hunk parsing is pure, string-in/list-out logic that deserves its own tests without any git, GitHub, or graph setup.

---

### Task 1: Test harness and metrics

Nothing in this repo is currently tested and pytest is not installed. This task establishes the harness and delivers the smallest real module through it, so the TDD cycle is proven working before anything complex depends on it.

**Files:**
- Create: `backend/requirements-dev.txt`
- Create: `backend/pytest.ini`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/services/metrics.py`
- Test: `backend/tests/test_metrics.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `metrics.stage(name: str) -> ContextManager[None]` — times a block
  - `metrics.RunMetrics` — `.record: dict`, `.stage(name)`, `.set(**fields)`, `.write(path: Path | None = None) -> dict`
  - `metrics.METRICS_PATH: Path` — default `backend/data/metrics.jsonl`

- [ ] **Step 1: Create the dev requirements file**

`backend/requirements-dev.txt`:

```
pytest>=8.0
httpx>=0.28
```

`httpx` is required by FastAPI's `TestClient`, used from Task 8 onward.

- [ ] **Step 2: Install dev dependencies**

Run from `backend/`:

```bash
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
```

Expected: pytest and httpx install successfully.

- [ ] **Step 3: Create pytest configuration**

`backend/pytest.ini`:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -v
```

`testpaths = tests` keeps pytest from crawling `.venv/`, which contains thousands of vendored test files and would otherwise dominate collection.

- [ ] **Step 4: Create the empty test package and shared fixtures**

`backend/tests/__init__.py`: empty file.

`backend/tests/conftest.py`:

```python
import sys
from pathlib import Path

# Tests import `services.*` the same way the app does, so the backend
# directory must be on sys.path regardless of where pytest was invoked.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
```

- [ ] **Step 5: Write the failing test**

`backend/tests/test_metrics.py`:

```python
import json

from services import metrics


def test_stage_records_duration_for_each_stage(tmp_path):
    run = metrics.RunMetrics(repo="owner/repo", pr=7)

    with run.stage("fetch"):
        pass
    with run.stage("parse"):
        pass

    assert "fetch_ms" in run.record
    assert "parse_ms" in run.record
    assert run.record["fetch_ms"] >= 0
    assert run.record["parse_ms"] >= 0


def test_set_adds_arbitrary_fields(tmp_path):
    run = metrics.RunMetrics(repo="owner/repo", pr=7)
    run.set(cache_hits=42, cache_misses=3)

    assert run.record["cache_hits"] == 42
    assert run.record["cache_misses"] == 3


def test_write_appends_one_json_object_per_run(tmp_path):
    target = tmp_path / "metrics.jsonl"

    first = metrics.RunMetrics(repo="a/b", pr=1)
    first.write(target)
    second = metrics.RunMetrics(repo="a/b", pr=2)
    second.write(target)

    lines = target.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["pr"] == 1
    assert json.loads(lines[1])["pr"] == 2


def test_write_records_total_and_timestamp(tmp_path):
    target = tmp_path / "metrics.jsonl"
    run = metrics.RunMetrics(repo="a/b", pr=1)
    written = run.write(target)

    assert "total_ms" in written
    assert "timestamp" in written
```

- [ ] **Step 6: Run the test to verify it fails**

Run from `backend/`:

```bash
.venv/Scripts/python.exe -m pytest tests/test_metrics.py -v
```

Expected: FAIL — `ImportError: cannot import name 'metrics' from 'services'`.

- [ ] **Step 7: Write the implementation**

`backend/services/metrics.py`:

```python
"""Per-run stage timings, appended as JSON Lines.

One record per analysis. The benchmark in `benchmarks/bench_pr.py` reads
this file to produce the before/after comparison table, so every field
added here is a field the benchmark can report on.
"""

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
METRICS_PATH = Path(os.environ.get("METRICS_PATH", BASE_DIR / "data" / "metrics.jsonl"))


class RunMetrics:
    """Collects timings and counters for a single analysis run."""

    def __init__(self, **fields: Any) -> None:
        self._started = time.perf_counter()
        self.record: Dict[str, Any] = dict(fields)

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        """Times a block and stores it as `<name>_ms`."""
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            self.record[f"{name}_ms"] = round(elapsed, 2)

    def set(self, **fields: Any) -> None:
        self.record.update(fields)

    def write(self, path: Optional[Path] = None) -> Dict[str, Any]:
        """Finalizes the record and appends it as one JSON line."""
        target = Path(path) if path is not None else METRICS_PATH
        self.record["total_ms"] = round((time.perf_counter() - self._started) * 1000, 2)
        self.record["timestamp"] = datetime.now(timezone.utc).isoformat()

        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(self.record) + "\n")
        return self.record
```

- [ ] **Step 8: Run the test to verify it passes**

```bash
.venv/Scripts/python.exe -m pytest tests/test_metrics.py -v
```

Expected: 4 passed.

- [ ] **Step 9: Ignore runtime artifacts**

Append to `.gitignore`, below the existing `backend/metadata/` line:

```
backend/cache/
backend/data/
```

- [ ] **Step 10: Commit**

```bash
git add backend/requirements-dev.txt backend/pytest.ini backend/tests backend/services/metrics.py .gitignore
git commit -m "test: add pytest harness and per-run metrics module"
```

---

### Task 2: Resolver indexes in the graph builder

Decision 4. Two nested scans become dictionary lookups. This is what makes rebuilding the graph on every analysis affordable, which is what lets us avoid the incorrect incremental patching described in Decision 1.

The golden test is the point of this task: it proves the faster builder produces a byte-identical graph.

**Files:**
- Create: `backend/tests/reference_graph.py` (verbatim copy of today's builder, kept as the oracle)
- Test: `backend/tests/test_graph_indexes.py`
- Modify: `backend/services/graph.py:122-248`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `graph.build_graph(project_id: str) -> DependencyGraph` — unchanged signature
  - `graph.build_graph_from_metadata(metadata_path: Path) -> DependencyGraph` — new, testable without a project id

- [ ] **Step 1: Create the reference builder**

Create `backend/tests/reference_graph.py` containing a function
`build_graph_reference(metadata_path)` that is a **verbatim copy** of the body of
today's `build_graph` (`backend/services/graph.py:122-248`), with two changes
only: it takes `metadata_path` directly instead of deriving it from a
`project_id`, and it imports `DependencyGraph` from `services.graph`.

```python
"""Frozen copy of the original graph builder, used as a correctness oracle.

Task 2 replaces the builder's nested scans with dictionary indexes. This
file preserves the pre-optimization behavior so the golden test can assert
the two produce identical graphs. Do not "improve" this file — its only
value is being unchanged.
"""

import json

from services.graph import DependencyGraph


def build_graph_reference(metadata_path):
    dg = DependencyGraph()

    if not metadata_path.exists():
        return dg

    discovered_functions = set()

    for meta_file in metadata_path.rglob("*.py.json"):
        with open(meta_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        file_path = data.get("relative_path", data.get("file_path", ""))
        file_path = file_path.replace("\\", "/")

        dg.add_file(file_path)

        for func in data.get("functions", []):
            func_name = func.get("full_name", func.get("name"))
            unique_id = f"{file_path}::{func_name}"
            dg.add_function(unique_id, file_path, func.get("lineno", 0))
            discovered_functions.add(unique_id)
            dg.add_dependency(file_path, unique_id, "contains")

    for meta_file in metadata_path.rglob("*.py.json"):
        with open(meta_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        file_path = data.get("relative_path", "").replace("\\", "/")

        for imp in data.get("imports", []):
            module_name = imp.get("from_module") or imp.get("module", "")
            if not module_name:
                continue

            module_path = module_name.replace(".", "/")
            candidates = (f"{module_path}.py", f"{module_path}/__init__.py")

            found = False
            for node_id in dg.graph.nodes:
                node = dg.graph.nodes[node_id]
                if node["type"] != "file":
                    continue
                for candidate in candidates:
                    if node_id == candidate or node_id.endswith("/" + candidate):
                        dg.add_dependency(file_path, node_id, "imports")
                        found = True
                        break
                if found:
                    break

        for func in data.get("functions", []):
            caller_name = func.get("full_name", func.get("name"))
            caller_id = f"{file_path}::{caller_name}"

            for call in func.get("calls", []):
                callee_name = call.get("name")

                local_callee_id = f"{file_path}::{callee_name}"
                if local_callee_id in discovered_functions:
                    dg.add_dependency(caller_id, local_callee_id, "calls")
                    continue

                potential_matches = []
                for potential_id in discovered_functions:
                    if potential_id.endswith(f"::{callee_name}"):
                        potential_matches.append(potential_id)

                if len(potential_matches) == 1:
                    dg.add_dependency(caller_id, potential_matches[0], "calls")
                elif len(potential_matches) > 1:
                    for match in potential_matches:
                        dg.add_dependency(caller_id, match, "calls_ambiguous")

    return dg
```

- [ ] **Step 2: Add a metadata-tree fixture**

Append to `backend/tests/conftest.py`:

```python
import json

import pytest


def write_metadata(metadata_root, relative_path, imports=None, functions=None):
    """Writes one metadata JSON file the way `analysis.parse_project` does."""
    target = metadata_root / (relative_path + ".json")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "file_path": relative_path,
        "relative_path": relative_path,
        "imports": imports or [],
        "classes": [],
        "functions": functions or [],
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


@pytest.fixture
def metadata_tree(tmp_path):
    """A metadata tree exercising local calls, unique calls, ambiguous calls,
    package imports and module imports."""
    root = tmp_path / "metadata"
    root.mkdir()

    write_metadata(
        root,
        "app/main.py",
        imports=[
            {"module": "app.store.save_user", "from_module": "app.store", "lineno": 1},
            {"module": "app.util", "lineno": 2},
        ],
        functions=[
            {
                "name": "handler",
                "full_name": "handler",
                "lineno": 5,
                "end_lineno": 12,
                "calls": [
                    {"name": "save_user", "lineno": 6},
                    {"name": "helper", "lineno": 7},
                    {"name": "log", "lineno": 8},
                ],
            },
            {"name": "helper", "full_name": "helper", "lineno": 14, "end_lineno": 16, "calls": []},
        ],
    )

    write_metadata(
        root,
        "app/store.py",
        functions=[
            {"name": "save_user", "full_name": "save_user", "lineno": 3, "end_lineno": 9, "calls": [{"name": "log", "lineno": 4}]},
            {"name": "log", "full_name": "log", "lineno": 11, "end_lineno": 12, "calls": []},
        ],
    )

    # A second `log` makes every non-local `log()` call ambiguous — this is
    # the global-resolution behavior that Decision 1 is about.
    write_metadata(
        root,
        "app/util/__init__.py",
        functions=[{"name": "log", "full_name": "log", "lineno": 1, "end_lineno": 2, "calls": []}],
    )

    return root
```

- [ ] **Step 3: Write the failing golden test**

`backend/tests/test_graph_indexes.py`:

```python
from services.graph import build_graph_from_metadata

from tests.reference_graph import build_graph_reference


def _snapshot(dg):
    nodes = sorted((nid, tuple(sorted(data.items()))) for nid, data in dg.graph.nodes(data=True))
    edges = sorted((s, t, tuple(sorted(data.items()))) for s, t, data in dg.graph.edges(data=True))
    return nodes, edges


def test_indexed_builder_matches_reference_builder(metadata_tree):
    fast = build_graph_from_metadata(metadata_tree)
    reference = build_graph_reference(metadata_tree)

    assert _snapshot(fast) == _snapshot(reference)


def test_ambiguous_calls_are_still_marked_ambiguous(metadata_tree):
    dg = build_graph_from_metadata(metadata_tree)

    edge_types = {
        (s, t): data["type"] for s, t, data in dg.graph.edges(data=True)
    }
    # Two functions named `log` exist, so the call from handler resolves to
    # both, as calls_ambiguous.
    assert edge_types[("app/main.py::handler", "app/store.py::log")] == "calls_ambiguous"
    assert edge_types[("app/main.py::handler", "app/util/__init__.py::log")] == "calls_ambiguous"


def test_local_call_resolves_locally_not_globally(metadata_tree):
    dg = build_graph_from_metadata(metadata_tree)
    edge = dg.graph.edges[("app/main.py::handler", "app/main.py::helper")]
    assert edge["type"] == "calls"


def test_from_module_import_resolves_to_package_init(metadata_tree):
    dg = build_graph_from_metadata(metadata_tree)
    assert dg.graph.has_edge("app/main.py", "app/store.py")


def test_missing_metadata_directory_yields_empty_graph(tmp_path):
    dg = build_graph_from_metadata(tmp_path / "does-not-exist")
    assert dg.graph.number_of_nodes() == 0
```

- [ ] **Step 4: Run the test to verify it fails**

```bash
.venv/Scripts/python.exe -m pytest tests/test_graph_indexes.py -v
```

Expected: FAIL — `ImportError: cannot import name 'build_graph_from_metadata'`.

- [ ] **Step 5: Replace the builder in `services/graph.py`**

Replace everything from `# --- Builder Logic ---` (line 120) to the end of the file with:

```python
# --- Builder Logic ---

def _load_metadata_documents(metadata_path: Path) -> List[Tuple[str, Dict]]:
    """Reads every metadata JSON once. The original builder read each file
    twice (once per pass); reading once and reusing halves the disk I/O."""
    documents = []
    for meta_file in metadata_path.rglob("*.py.json"):
        with open(meta_file, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        file_path = data.get("relative_path", data.get("file_path", ""))
        documents.append((file_path.replace("\\", "/"), data))
    return documents


def _resolve_import_target(module_name: str, file_index: Dict[str, str]) -> Optional[str]:
    """Maps a module name to a file node id via the prebuilt index.

    The original scanned every file node per import. `file_index` maps both
    'a/b.py' and 'a/b/__init__.py' shapes plus each of their path suffixes,
    so resolution is a dict lookup with the same matching semantics:
    exact id, or a match on a '/'-delimited path boundary.
    """
    module_path = module_name.replace(".", "/")
    for candidate in (f"{module_path}.py", f"{module_path}/__init__.py"):
        target = file_index.get(candidate)
        if target is not None:
            return target
    return None


def build_graph_from_metadata(metadata_path: Path) -> DependencyGraph:
    """Constructs the dependency graph from computed metadata.

    Call resolution here is *global*: a callee name is matched against every
    known function in the repository. That is why the graph is rebuilt in
    full on every analysis rather than patched per changed file — adding a
    function anywhere can flip call sites in files that did not change.
    See Decision 1 in the design spec.
    """
    dg = DependencyGraph()

    if not metadata_path.exists():
        return dg

    documents = _load_metadata_documents(metadata_path)

    # --- Pass 1: nodes, plus the indexes that make pass 2 linear ---
    # name -> [function ids], for call resolution.
    name_index: Dict[str, List[str]] = {}
    # candidate path -> file node id, for import resolution.
    file_index: Dict[str, str] = {}
    discovered_functions = set()

    for file_path, data in documents:
        dg.add_file(file_path)

        # Register every '/'-delimited suffix so `endswith("/" + candidate)`
        # becomes a lookup. Registered shortest-first so that, as in the
        # original's node-iteration order, an exact id wins.
        segments = file_path.split("/")
        for start in range(len(segments)):
            file_index.setdefault("/".join(segments[start:]), file_path)

        for func in data.get("functions", []):
            func_name = func.get("full_name", func.get("name"))
            unique_id = f"{file_path}::{func_name}"

            dg.add_function(unique_id, file_path, func.get("lineno", 0))
            discovered_functions.add(unique_id)
            dg.add_dependency(file_path, unique_id, "contains")

            # A call site writes `save_user` or `Class.method`; index the
            # trailing segment after '::' exactly as the original matched it.
            name_index.setdefault(func_name, []).append(unique_id)

    # --- Pass 2: edges ---
    for file_path, data in documents:
        for imp in data.get("imports", []):
            module_name = imp.get("from_module") or imp.get("module", "")
            if not module_name:
                continue
            target = _resolve_import_target(module_name, file_index)
            if target is not None:
                dg.add_dependency(file_path, target, "imports")

        for func in data.get("functions", []):
            caller_name = func.get("full_name", func.get("name"))
            caller_id = f"{file_path}::{caller_name}"

            for call in func.get("calls", []):
                callee_name = call.get("name")

                local_callee_id = f"{file_path}::{callee_name}"
                if local_callee_id in discovered_functions:
                    dg.add_dependency(caller_id, local_callee_id, "calls")
                    continue

                matches = name_index.get(callee_name, [])
                if len(matches) == 1:
                    dg.add_dependency(caller_id, matches[0], "calls")
                elif len(matches) > 1:
                    # False positives are safer than false negatives for a
                    # blast-radius tool, so link all candidates but mark them.
                    for match in matches:
                        dg.add_dependency(caller_id, match, "calls_ambiguous")

    return dg


def build_graph(project_id: str) -> DependencyGraph:
    """Constructs the dependency graph for a project id."""
    return build_graph_from_metadata(get_metadata_path(project_id))
```

- [ ] **Step 6: Run the golden test**

```bash
.venv/Scripts/python.exe -m pytest tests/test_graph_indexes.py -v
```

Expected: 5 passed. **If `test_indexed_builder_matches_reference_builder` fails, do not proceed and do not adjust the reference file.** The reference is the oracle. Read the diff between the two snapshots and fix `build_graph_from_metadata`.

One known divergence to watch for: the original matched a function name against `discovered_functions`, a *set*, so multi-match ordering was arbitrary; `name_index` preserves document order. Because the test compares sorted edge lists, ordering does not affect the result — but if you see a count mismatch rather than an ordering one, the indexes are wrong.

- [ ] **Step 7: Verify the whole suite still passes**

```bash
.venv/Scripts/python.exe -m pytest -v
```

Expected: 9 passed.

- [ ] **Step 8: Commit**

```bash
git add backend/services/graph.py backend/tests/reference_graph.py backend/tests/test_graph_indexes.py backend/tests/conftest.py
git commit -m "perf: index graph resolver, pinned by golden equivalence test"
```

---

### Task 3: Repository cache

Decision 2. Deterministic keys and clone reuse — the largest single wall-clock win, and the change that makes every other cache layer possible.

**Files:**
- Create: `backend/services/repo_cache.py`
- Test: `backend/tests/test_repo_cache.py`
- Modify: `backend/tests/conftest.py` (add the git repo fixture)

**Interfaces:**
- Consumes: nothing
- Produces:
  - `repo_cache.project_key(repo_full_name: str) -> str` — 16-char hex
  - `repo_cache.ensure_repo(repo_full_name: str, clone_url: str, ref: str) -> tuple[Path, bool]` — returns (path, was_cloned); `was_cloned` is False when an existing clone was reused
  - `repo_cache.tree_blobs(repo_path: Path) -> dict[str, str]` — relative posix path → blob SHA, `.py` files only

- [ ] **Step 1: Add the git repository fixture**

Append to `backend/tests/conftest.py`:

```python
import subprocess


def git(repo_path, *args):
    """Runs a git command in `repo_path`, raising on failure."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout


@pytest.fixture
def origin_repo(tmp_path):
    """A real two-commit git repository to clone from.

    The feature is about git object behavior — blob SHAs, checkout, refs — so
    mocking git would only test the mock. A temp repo is fast and real.
    """
    repo = tmp_path / "origin"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")

    (repo / "app").mkdir()
    (repo / "app" / "main.py").write_text("def handler():\n    return store_it()\n", encoding="utf-8")
    (repo / "app" / "store.py").write_text("def store_it():\n    return 1\n", encoding="utf-8")
    (repo / "README.md").write_text("not python\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "first")
    first_sha = git(repo, "rev-parse", "HEAD").strip()

    (repo / "app" / "store.py").write_text("def store_it():\n    return 2\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "second")
    second_sha = git(repo, "rev-parse", "HEAD").strip()

    return {"path": repo, "url": repo.as_uri(), "first": first_sha, "second": second_sha}
```

- [ ] **Step 2: Write the failing test**

`backend/tests/test_repo_cache.py`:

```python
import pytest

from services import repo_cache


def test_project_key_is_stable_and_case_insensitive():
    assert repo_cache.project_key("Owner/Repo") == repo_cache.project_key("owner/repo")
    assert repo_cache.project_key("owner/repo") == repo_cache.project_key("owner/repo")


def test_project_key_differs_per_repo():
    assert repo_cache.project_key("a/b") != repo_cache.project_key("a/c")


def test_project_key_is_filesystem_safe():
    key = repo_cache.project_key("owner/repo")
    assert key.isalnum()
    assert len(key) == 16


def test_first_call_clones_and_second_call_reuses(tmp_path, origin_repo, monkeypatch):
    monkeypatch.setattr(repo_cache, "STORAGE_ROOT", tmp_path / "storage")

    path_one, cloned_one = repo_cache.ensure_repo("owner/repo", origin_repo["url"], origin_repo["second"])
    assert cloned_one is True
    assert (path_one / "app" / "main.py").exists()

    path_two, cloned_two = repo_cache.ensure_repo("owner/repo", origin_repo["url"], origin_repo["second"])
    assert cloned_two is False
    assert path_two == path_one


def test_ensure_repo_checks_out_the_requested_sha(tmp_path, origin_repo, monkeypatch):
    monkeypatch.setattr(repo_cache, "STORAGE_ROOT", tmp_path / "storage")

    path, _ = repo_cache.ensure_repo("owner/repo", origin_repo["url"], origin_repo["first"])
    assert (path / "app" / "store.py").read_text(encoding="utf-8") == "def store_it():\n    return 1\n"

    path, _ = repo_cache.ensure_repo("owner/repo", origin_repo["url"], origin_repo["second"])
    assert (path / "app" / "store.py").read_text(encoding="utf-8") == "def store_it():\n    return 2\n"


def test_tree_blobs_lists_python_files_only(tmp_path, origin_repo, monkeypatch):
    monkeypatch.setattr(repo_cache, "STORAGE_ROOT", tmp_path / "storage")
    path, _ = repo_cache.ensure_repo("owner/repo", origin_repo["url"], origin_repo["second"])

    blobs = repo_cache.tree_blobs(path)

    assert set(blobs) == {"app/main.py", "app/store.py"}
    assert all(len(sha) == 40 for sha in blobs.values())


def test_tree_blobs_changes_only_for_changed_files(tmp_path, origin_repo, monkeypatch):
    monkeypatch.setattr(repo_cache, "STORAGE_ROOT", tmp_path / "storage")

    path, _ = repo_cache.ensure_repo("owner/repo", origin_repo["url"], origin_repo["first"])
    before = repo_cache.tree_blobs(path)
    path, _ = repo_cache.ensure_repo("owner/repo", origin_repo["url"], origin_repo["second"])
    after = repo_cache.tree_blobs(path)

    assert before["app/main.py"] == after["app/main.py"]
    assert before["app/store.py"] != after["app/store.py"]


def test_unreachable_remote_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(repo_cache, "STORAGE_ROOT", tmp_path / "storage")

    with pytest.raises(repo_cache.RepoCacheError):
        repo_cache.ensure_repo("owner/nope", (tmp_path / "missing").as_uri(), "HEAD")
```

`test_tree_blobs_changes_only_for_changed_files` is the important one: it is the
property the entire parse cache depends on.

- [ ] **Step 3: Run the test to verify it fails**

```bash
.venv/Scripts/python.exe -m pytest tests/test_repo_cache.py -v
```

Expected: FAIL — `ImportError: cannot import name 'repo_cache'`.

- [ ] **Step 4: Write the implementation**

`backend/services/repo_cache.py`:

```python
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
from typing import Dict, Tuple

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


def ensure_repo(repo_full_name: str, clone_url: str, ref: str) -> Tuple[Path, bool]:
    """Ensures a clone exists at `ref`. Returns (path, was_cloned)."""
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
            if not was_cloned:
                repo.git.fetch("origin", "--prune", "--tags", "--force")
            repo.git.checkout(ref, force=True)
    except Exception as exc:
        raise RepoCacheError(f"Failed to check out {ref} for {repo_full_name}: {exc}") from exc

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
```

Note the clone is **not** shallow. `depth=1` would save time on the first
clone but breaks checking out an arbitrary PR head SHA later — and the whole
point of this module is that subsequent operations are cheap.

- [ ] **Step 5: Run the tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_repo_cache.py -v
```

Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/services/repo_cache.py backend/tests/test_repo_cache.py backend/tests/conftest.py
git commit -m "feat: deterministic repo keys with clone reuse"
```

---

### Task 4: Content-hash parse cache

Decision 3. Skip `ast.parse` for every file whose blob SHA is unchanged. This is the substance of the incremental-analysis claim.

**Files:**
- Create: `backend/services/parse_cache.py`
- Test: `backend/tests/test_parse_cache.py`

**Interfaces:**
- Consumes: `repo_cache.tree_blobs`, `analysis.get_metadata_path`, `parser.parse_file`
- Produces:
  - `parse_cache.CacheStats` — dataclass with `hits: int`, `misses: int`, `deleted: int`, `total: int`
  - `parse_cache.sync(project_key: str, repo_path: Path, blobs: dict[str, str]) -> CacheStats`
  - `parse_cache.index_path(project_key: str) -> Path`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_parse_cache.py`:

```python
import json

from services import parse_cache


def _seed(tmp_path, files):
    """Writes source files and returns a fake blob map keyed by content."""
    blobs = {}
    for relative, content in files.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        blobs[relative] = f"sha-{hash(content) & 0xFFFFFF:06x}"
    return blobs


def test_cold_start_parses_everything(tmp_path, monkeypatch):
    monkeypatch.setattr(parse_cache, "METADATA_ROOT", tmp_path / "metadata")
    monkeypatch.setattr(parse_cache, "CACHE_ROOT", tmp_path / "cache")
    repo = tmp_path / "repo"
    blobs = _seed(repo, {"a.py": "def one():\n    pass\n", "b.py": "def two():\n    pass\n"})

    stats = parse_cache.sync("key", repo, blobs)

    assert stats.misses == 2
    assert stats.hits == 0
    assert (tmp_path / "metadata" / "key" / "a.py.json").exists()


def test_second_run_with_no_changes_is_all_hits(tmp_path, monkeypatch):
    monkeypatch.setattr(parse_cache, "METADATA_ROOT", tmp_path / "metadata")
    monkeypatch.setattr(parse_cache, "CACHE_ROOT", tmp_path / "cache")
    repo = tmp_path / "repo"
    blobs = _seed(repo, {"a.py": "def one():\n    pass\n", "b.py": "def two():\n    pass\n"})

    parse_cache.sync("key", repo, blobs)
    stats = parse_cache.sync("key", repo, blobs)

    assert stats.hits == 2
    assert stats.misses == 0


def test_changed_blob_is_reparsed_and_others_are_not(tmp_path, monkeypatch):
    monkeypatch.setattr(parse_cache, "METADATA_ROOT", tmp_path / "metadata")
    monkeypatch.setattr(parse_cache, "CACHE_ROOT", tmp_path / "cache")
    repo = tmp_path / "repo"
    blobs = _seed(repo, {"a.py": "def one():\n    pass\n", "b.py": "def two():\n    pass\n"})
    parse_cache.sync("key", repo, blobs)

    (repo / "b.py").write_text("def two():\n    return renamed()\n", encoding="utf-8")
    blobs["b.py"] = "sha-changed"

    stats = parse_cache.sync("key", repo, blobs)

    assert stats.hits == 1
    assert stats.misses == 1
    metadata = json.loads((tmp_path / "metadata" / "key" / "b.py.json").read_text(encoding="utf-8"))
    assert metadata["functions"][0]["calls"][0]["name"] == "renamed"


def test_deleted_file_has_metadata_evicted(tmp_path, monkeypatch):
    monkeypatch.setattr(parse_cache, "METADATA_ROOT", tmp_path / "metadata")
    monkeypatch.setattr(parse_cache, "CACHE_ROOT", tmp_path / "cache")
    repo = tmp_path / "repo"
    blobs = _seed(repo, {"a.py": "def one():\n    pass\n", "b.py": "def two():\n    pass\n"})
    parse_cache.sync("key", repo, blobs)

    del blobs["b.py"]
    stats = parse_cache.sync("key", repo, blobs)

    assert stats.deleted == 1
    assert not (tmp_path / "metadata" / "key" / "b.py.json").exists()


def test_metadata_carries_relative_path_for_the_graph_builder(tmp_path, monkeypatch):
    monkeypatch.setattr(parse_cache, "METADATA_ROOT", tmp_path / "metadata")
    monkeypatch.setattr(parse_cache, "CACHE_ROOT", tmp_path / "cache")
    repo = tmp_path / "repo"
    blobs = _seed(repo, {"pkg/mod.py": "def one():\n    pass\n"})

    parse_cache.sync("key", repo, blobs)

    metadata = json.loads((tmp_path / "metadata" / "key" / "pkg" / "mod.py.json").read_text(encoding="utf-8"))
    assert metadata["relative_path"] == "pkg/mod.py"


def test_missing_metadata_file_forces_reparse_despite_index_hit(tmp_path, monkeypatch):
    monkeypatch.setattr(parse_cache, "METADATA_ROOT", tmp_path / "metadata")
    monkeypatch.setattr(parse_cache, "CACHE_ROOT", tmp_path / "cache")
    repo = tmp_path / "repo"
    blobs = _seed(repo, {"a.py": "def one():\n    pass\n"})
    parse_cache.sync("key", repo, blobs)

    (tmp_path / "metadata" / "key" / "a.py.json").unlink()
    stats = parse_cache.sync("key", repo, blobs)

    assert stats.misses == 1
```

The last test matters: the index and the metadata files can drift (a crash
between writes, a partial deploy). The index alone must never be trusted.

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/Scripts/python.exe -m pytest tests/test_parse_cache.py -v
```

Expected: FAIL — `ImportError: cannot import name 'parse_cache'`.

- [ ] **Step 3: Write the implementation**

`backend/services/parse_cache.py`:

```python
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
```

Note `result["relative_path"]` uses the forward-slash path directly. The graph
builder reads that field (`graph.py`), so it must match the node id format.

- [ ] **Step 4: Run the tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_parse_cache.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/services/parse_cache.py backend/tests/test_parse_cache.py
git commit -m "feat: content-hash parse cache keyed by git blob SHA"
```

---

### Task 5: Diff-to-function mapping

Turns a unified diff patch into the set of functions a PR actually touched. Pure logic — no git, no HTTP, no graph.

**Files:**
- Create: `backend/services/diff_map.py`
- Test: `backend/tests/test_diff_map.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `diff_map.changed_line_ranges(patch: str) -> list[tuple[int, int]]` — inclusive new-side ranges
  - `diff_map.touched_functions(metadata: dict, ranges: list[tuple[int, int]]) -> list[str]` — `full_name` values, in file order

- [ ] **Step 1: Write the failing test**

`backend/tests/test_diff_map.py`:

```python
from services import diff_map

PATCH = """@@ -1,4 +1,6 @@
 import os
+import sys
 
 def alpha():
-    return 1
+    return 2
@@ -20,3 +22,4 @@ def beta():
     pass
+    # touched
"""


def test_changed_line_ranges_parses_every_hunk():
    ranges = diff_map.changed_line_ranges(PATCH)
    assert ranges == [(1, 6), (22, 25)]


def test_hunk_without_a_count_defaults_to_one_line():
    ranges = diff_map.changed_line_ranges("@@ -5 +7 @@\n-old\n+new\n")
    assert ranges == [(7, 7)]


def test_empty_patch_yields_no_ranges():
    assert diff_map.changed_line_ranges("") == []
    assert diff_map.changed_line_ranges(None) == []


def test_deleted_file_hunk_with_zero_new_lines_is_ignored():
    assert diff_map.changed_line_ranges("@@ -1,3 +0,0 @@\n-gone\n") == []


METADATA = {
    "relative_path": "app/main.py",
    "functions": [
        {"name": "alpha", "full_name": "alpha", "lineno": 4, "end_lineno": 8},
        {"name": "beta", "full_name": "beta", "lineno": 10, "end_lineno": 14},
        {"name": "run", "full_name": "Worker.run", "lineno": 20, "end_lineno": 30},
    ],
}


def test_touched_functions_finds_the_enclosing_function():
    assert diff_map.touched_functions(METADATA, [(5, 5)]) == ["alpha"]


def test_touched_functions_returns_all_overlapped_functions():
    assert diff_map.touched_functions(METADATA, [(7, 12)]) == ["alpha", "beta"]


def test_change_outside_any_function_touches_nothing():
    assert diff_map.touched_functions(METADATA, [(1, 2)]) == []


def test_qualified_names_are_returned_as_stored():
    assert diff_map.touched_functions(METADATA, [(25, 25)]) == ["Worker.run"]


def test_function_missing_end_lineno_falls_back_to_its_start_line():
    metadata = {"functions": [{"name": "x", "full_name": "x", "lineno": 3}]}
    assert diff_map.touched_functions(metadata, [(3, 3)]) == ["x"]
    assert diff_map.touched_functions(metadata, [(4, 4)]) == []


def test_results_are_deduplicated():
    assert diff_map.touched_functions(METADATA, [(5, 5), (6, 6)]) == ["alpha"]
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/Scripts/python.exe -m pytest tests/test_diff_map.py -v
```

Expected: FAIL — `ImportError: cannot import name 'diff_map'`.

- [ ] **Step 3: Write the implementation**

`backend/services/diff_map.py`:

```python
"""Maps a unified diff to the functions it touched.

Uses exact `lineno`/`end_lineno` spans from the AST rather than git's
`@@ ... @@` trailing context hint — that hint is an indentation heuristic and
is frequently wrong for decorated or nested definitions. We already have
exact spans, so we use them.
"""

import re
from typing import Dict, List, Optional, Tuple

# "@@ -old,count +new,count @@" — the new-side count is optional and
# defaults to 1 when git omits it for a single-line hunk.
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def changed_line_ranges(patch: Optional[str]) -> List[Tuple[int, int]]:
    """Inclusive new-side line ranges from every hunk header in `patch`."""
    if not patch:
        return []

    ranges: List[Tuple[int, int]] = []
    for line in patch.splitlines():
        match = _HUNK.match(line)
        if not match:
            continue
        start = int(match.group(1))
        count = int(match.group(2)) if match.group(2) is not None else 1
        if count == 0:
            # Pure deletion: nothing exists on the new side to attribute.
            continue
        ranges.append((start, start + count - 1))
    return ranges


def touched_functions(metadata: Dict, ranges: List[Tuple[int, int]]) -> List[str]:
    """Function `full_name`s whose body overlaps any changed range.

    Order follows the metadata (i.e. file order) and duplicates are removed,
    so the report is stable across runs.
    """
    if not ranges:
        return []

    touched: List[str] = []
    for func in metadata.get("functions", []):
        start = func.get("lineno", 0)
        end = func.get("end_lineno") or start
        name = func.get("full_name", func.get("name"))
        if name is None:
            continue
        for range_start, range_end in ranges:
            if range_start <= end and start <= range_end:
                if name not in touched:
                    touched.append(name)
                break
    return touched
```

- [ ] **Step 4: Run the tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_diff_map.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/services/diff_map.py backend/tests/test_diff_map.py
git commit -m "feat: map diff hunks to touched function spans"
```

---

### Task 6: GitHub App client

App authentication and the four REST calls we need. Kept free of any analysis logic so it can be tested without a graph, and so the analysis can be tested without GitHub.

**Files:**
- Create: `backend/services/github_app.py`
- Test: `backend/tests/test_github_app.py`
- Modify: `backend/requirements.txt`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `github_app.GitHubAppError` — exception
  - `github_app.app_jwt() -> str`
  - `github_app.installation_token(installation_id: int) -> str` — cached until 60s before expiry
  - `github_app.pr_files(repo_full_name: str, pr_number: int, token: str | None) -> list[dict]`
  - `github_app.pull_request(repo_full_name: str, pr_number: int, token: str | None) -> dict`
  - `github_app.upsert_comment(repo_full_name: str, pr_number: int, body: str, token: str) -> dict`
  - `github_app.post_check_run(repo_full_name: str, head_sha: str, title: str, summary: str, conclusion: str, token: str) -> dict`
  - `github_app.COMMENT_MARKER: str`

- [ ] **Step 1: Add the runtime dependencies**

Append to `backend/requirements.txt`:

```
PyJWT>=2.9
cryptography>=43
```

Install:

```bash
.venv/Scripts/python.exe -m pip install "PyJWT>=2.9" "cryptography>=43"
```

`cryptography` is required for RS256; PyJWT alone only supports HMAC algorithms.

- [ ] **Step 2: Write the failing test**

`backend/tests/test_github_app.py`:

```python
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
        github_app.requests, "get", lambda *a, **k: FakeResponse({"message": "Not Found"}, status=404)
    )
    with pytest.raises(github_app.GitHubAppError):
        github_app.pull_request("o/r", 1, token=None)
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
.venv/Scripts/python.exe -m pytest tests/test_github_app.py -v
```

Expected: FAIL — `ImportError: cannot import name 'github_app'`.

- [ ] **Step 4: Write the implementation**

`backend/services/github_app.py`:

```python
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
        raise GitHubAppError(f"{context} failed with {response.status_code}: {response.text[:300]}")
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
        response = requests.get(url, headers=_headers(token), params={"per_page": 100}, timeout=TIMEOUT)
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
```

- [ ] **Step 5: Run the tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_github_app.py -v
```

Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/services/github_app.py backend/tests/test_github_app.py backend/requirements.txt
git commit -m "feat: GitHub App auth and REST client with comment upsert"
```

---

### Task 7: PR analysis orchestration

Wires the previous tasks into one function. This is the core deliverable — everything before it was a component, everything after it is a trigger.

**Files:**
- Create: `backend/services/pr_report.py`
- Test: `backend/tests/test_pr_report.py`

**Interfaces:**
- Consumes: `repo_cache`, `parse_cache`, `diff_map`, `graph.build_graph_from_metadata`, `metrics`, `github_app.pr_files`
- Produces:
  - `pr_report.PRImpact` — dataclass: `repo: str`, `pr: int`, `head_sha: str`, `changed_files: list[str]`, `targets: list[str]`, `impacted: list[dict]`, `impacted_files: list[str]`, `stats: dict`
  - `pr_report.analyze_pr(repo_full_name, pr_number, head_sha, clone_url, token=None, files=None) -> PRImpact`
  - `pr_report.render_markdown(impact: PRImpact) -> str`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_pr_report.py`:

```python
import pytest

from services import github_app, parse_cache, pr_report, repo_cache

CALLER_PATCH = "@@ -1,2 +1,3 @@\n def store_it():\n-    return 1\n+    return 2\n"


@pytest.fixture
def isolated_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(repo_cache, "STORAGE_ROOT", tmp_path / "storage")
    monkeypatch.setattr(parse_cache, "METADATA_ROOT", tmp_path / "metadata")
    monkeypatch.setattr(parse_cache, "CACHE_ROOT", tmp_path / "cache")
    monkeypatch.setattr(pr_report.metrics, "METRICS_PATH", tmp_path / "metrics.jsonl")
    return tmp_path


def test_analyze_pr_finds_callers_of_a_changed_function(isolated_roots, origin_repo, monkeypatch):
    monkeypatch.setattr(
        github_app,
        "pr_files",
        lambda repo, pr, token: [{"filename": "app/store.py", "status": "modified", "patch": CALLER_PATCH}],
    )

    impact = pr_report.analyze_pr(
        "owner/repo", 7, origin_repo["second"], origin_repo["url"], token=None
    )

    assert impact.targets == ["app/store.py::store_it"]
    assert "app/main.py::handler" in [node["id"] for node in impact.impacted]
    assert "app/main.py" in impact.impacted_files


def test_second_analysis_reuses_clone_and_hits_the_parse_cache(isolated_roots, origin_repo, monkeypatch):
    monkeypatch.setattr(
        github_app,
        "pr_files",
        lambda repo, pr, token: [{"filename": "app/store.py", "status": "modified", "patch": CALLER_PATCH}],
    )

    first = pr_report.analyze_pr("owner/repo", 7, origin_repo["second"], origin_repo["url"], token=None)
    second = pr_report.analyze_pr("owner/repo", 7, origin_repo["second"], origin_repo["url"], token=None)

    assert first.stats["cloned"] is True
    assert first.stats["cache_misses"] == 2
    assert second.stats["cloned"] is False
    assert second.stats["cache_hits"] == 2
    assert second.stats["cache_misses"] == 0


def test_non_python_files_are_ignored(isolated_roots, origin_repo, monkeypatch):
    monkeypatch.setattr(
        github_app,
        "pr_files",
        lambda repo, pr, token: [{"filename": "README.md", "status": "modified", "patch": "@@ -1 +1,2 @@\n+x\n"}],
    )

    impact = pr_report.analyze_pr("owner/repo", 7, origin_repo["second"], origin_repo["url"], token=None)

    assert impact.targets == []
    assert impact.impacted == []


def test_module_level_change_falls_back_to_the_file_node(isolated_roots, origin_repo, monkeypatch):
    # A hunk at line 1 of main.py sits outside any function body.
    monkeypatch.setattr(
        github_app,
        "pr_files",
        lambda repo, pr, token: [
            {"filename": "app/main.py", "status": "modified", "patch": "@@ -1,0 +1,1 @@\n+import os\n"}
        ],
    )

    impact = pr_report.analyze_pr("owner/repo", 7, origin_repo["second"], origin_repo["url"], token=None)

    assert impact.targets == ["app/main.py"]


def test_metrics_record_is_written_per_run(isolated_roots, origin_repo, monkeypatch):
    monkeypatch.setattr(
        github_app,
        "pr_files",
        lambda repo, pr, token: [{"filename": "app/store.py", "status": "modified", "patch": CALLER_PATCH}],
    )

    pr_report.analyze_pr("owner/repo", 7, origin_repo["second"], origin_repo["url"], token=None)

    lines = (isolated_roots / "metrics.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert "parse_ms" in lines[0]
    assert "graph_ms" in lines[0]


def test_render_markdown_names_impacted_functions(isolated_roots, origin_repo, monkeypatch):
    monkeypatch.setattr(
        github_app,
        "pr_files",
        lambda repo, pr, token: [{"filename": "app/store.py", "status": "modified", "patch": CALLER_PATCH}],
    )

    impact = pr_report.analyze_pr("owner/repo", 7, origin_repo["second"], origin_repo["url"], token=None)
    body = pr_report.render_markdown(impact)

    assert "store_it" in body
    assert "handler" in body
    assert "Impact Lens" in body


def test_render_markdown_handles_an_empty_blast_radius(isolated_roots, origin_repo, monkeypatch):
    monkeypatch.setattr(
        github_app, "pr_files", lambda repo, pr, token: [{"filename": "README.md", "patch": "@@ -1 +1,2 @@\n+x\n"}]
    )

    impact = pr_report.analyze_pr("owner/repo", 7, origin_repo["second"], origin_repo["url"], token=None)
    body = pr_report.render_markdown(impact)

    assert "No Python changes" in body
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/Scripts/python.exe -m pytest tests/test_pr_report.py -v
```

Expected: FAIL — `ImportError: cannot import name 'pr_report'`.

- [ ] **Step 3: Write the implementation**

`backend/services/pr_report.py`:

```python
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
        pr_file_entries = files if files is not None else github_app.pr_files(
            repo_full_name, pr_number, token
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
        return (
            "## Impact Lens\n\n"
            "No Python changes to analyze in this pull request.\n"
        )

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
        lines += ["", "### Blast radius", "", "| Depends on your change | Depth | Confidence |", "|---|---|---|"]
        for node in impact.impacted[:MAX_LISTED_IMPACTS]:
            lines.append(f"| `{node['id']}` | {node['depth']} | {node.get('confidence', 'direct')} |")
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
```

- [ ] **Step 4: Run the tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_pr_report.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Run the whole suite**

```bash
.venv/Scripts/python.exe -m pytest -v
```

Expected: 48 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/services/pr_report.py backend/tests/test_pr_report.py
git commit -m "feat: PR blast-radius analysis with cached incremental parsing"
```

---

### Task 8: Webhook endpoint and manual trigger

Decision 5 and 6. Two thin transports over the one `analyze_pr()` function.

**Files:**
- Create: `backend/services/pr_webhook.py`
- Test: `backend/tests/test_pr_webhook.py`
- Modify: `backend/main.py`

**Interfaces:**
- Consumes: `pr_report.analyze_pr`, `github_app`
- Produces:
  - `pr_webhook.router` — FastAPI `APIRouter`
  - `pr_webhook.verify_signature(secret: str, body: bytes, header: str | None) -> bool`
  - `pr_webhook.seen_delivery(delivery_id: str) -> bool`
  - `pr_webhook.handle_pull_request(payload: dict) -> None`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_pr_webhook.py`:

```python
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
        "repository": {"full_name": "owner/repo", "clone_url": "https://github.com/owner/repo.git"},
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
        data=body,
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

    first = client.post("/api/github/webhook", data=body, headers=headers)
    second = client.post("/api/github/webhook", data=body, headers=headers)

    assert first.status_code == 202
    assert second.status_code == 200
    assert len(calls) == 1


def test_irrelevant_action_is_ignored(client, monkeypatch):
    calls = []
    monkeypatch.setattr(pr_webhook, "handle_pull_request", lambda payload: calls.append(payload))

    body = json.dumps(_payload(action="labeled")).encode()
    response = client.post(
        "/api/github/webhook",
        data=body,
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
        data=body,
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
        stats={"cloned": False, "cache_hits": 5, "cache_misses": 1, "cache_hit_ratio": 0.83, "files_total": 6, "total_ms": 120.0},
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/Scripts/python.exe -m pytest tests/test_pr_webhook.py -v
```

Expected: FAIL — `ImportError: cannot import name 'pr_webhook'`.

- [ ] **Step 3: Write the implementation**

`backend/services/pr_webhook.py`:

```python
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

        impact = pr_report.analyze_pr(repo_full_name, pr_number, head_sha, clone_url, token=token)
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
                    summary=f"Impact Lens failed to analyze this pull request.\n\n```\n{exc}\n```",
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
    from fastapi.responses import JSONResponse

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
    clone_url = details["head"]["repo"]["clone_url"]

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
```

- [ ] **Step 4: Mount the router**

In `backend/main.py`, after the CORS middleware block (line 23), add:

```python
from services.pr_webhook import router as pr_router

app.include_router(pr_router)
```

- [ ] **Step 5: Run the tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_pr_webhook.py -v
```

Expected: 12 passed.

- [ ] **Step 6: Run the whole suite**

```bash
.venv/Scripts/python.exe -m pytest -v
```

Expected: 60 passed.

- [ ] **Step 7: Commit**

```bash
git add backend/services/pr_webhook.py backend/tests/test_pr_webhook.py backend/main.py
git commit -m "feat: signed webhook endpoint and manual PR analysis trigger"
```

---

### Task 9: Benchmark harness

Produces the measured numbers. Until this runs, no speedup figure is quoted anywhere.

**Files:**
- Create: `backend/benchmarks/__init__.py`
- Create: `backend/benchmarks/bench_pr.py`
- Create: `backend/benchmarks/corpus.json`
- Test: `backend/tests/test_bench_pr.py`

**Interfaces:**
- Consumes: `pr_report.analyze_pr`, `parse_cache.clear`, `repo_cache`
- Produces:
  - `bench_pr.percentile(values: list[float], p: float) -> float`
  - `bench_pr.summarize(cold: list[float], warm: list[float], full: list[float], incremental: list[float]) -> dict`
  - `bench_pr.render_table(summary: dict) -> str`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_bench_pr.py`:

```python
import pytest

from benchmarks import bench_pr


def test_percentile_picks_the_nearest_rank():
    values = [10, 20, 30, 40, 50]
    assert bench_pr.percentile(values, 50) == 30
    assert bench_pr.percentile(values, 95) == 50


def test_percentile_of_a_single_value():
    assert bench_pr.percentile([7.5], 50) == 7.5


def test_percentile_of_empty_is_zero():
    assert bench_pr.percentile([], 50) == 0.0


def test_summarize_computes_both_reductions():
    summary = bench_pr.summarize(cold=[1000.0], warm=[200.0], full=[500.0], incremental=[250.0])

    assert summary["cold_vs_warm_reduction_pct"] == pytest.approx(80.0)
    assert summary["full_vs_incremental_reduction_pct"] == pytest.approx(50.0)


def test_summarize_reports_percentiles():
    summary = bench_pr.summarize(
        cold=[100.0, 200.0], warm=[10.0, 20.0], full=[50.0], incremental=[25.0]
    )
    assert summary["warm_p50_ms"] == 10.0
    assert summary["warm_p95_ms"] == 20.0


def test_summarize_with_no_samples_does_not_divide_by_zero():
    summary = bench_pr.summarize(cold=[], warm=[], full=[], incremental=[])
    assert summary["cold_vs_warm_reduction_pct"] == 0.0


def test_render_table_labels_each_baseline():
    summary = bench_pr.summarize(cold=[1000.0], warm=[200.0], full=[500.0], incremental=[250.0])
    table = bench_pr.render_table(summary)

    assert "Cold vs warm" in table
    assert "Full reparse vs incremental" in table
    assert "80.0" in table
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/Scripts/python.exe -m pytest tests/test_bench_pr.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'benchmarks'`.

- [ ] **Step 3: Write the corpus file**

`backend/benchmarks/corpus.json` — small, real, public Python repositories with
real merged PRs. Naming the corpus is what makes the numbers reproducible:

```json
[
  {"repo_url": "https://github.com/psf/requests", "pr_number": 6800},
  {"repo_url": "https://github.com/pallets/click", "pr_number": 2750},
  {"repo_url": "https://github.com/psf/black", "pr_number": 4400}
]
```

If any PR number no longer exists, replace it with a current merged PR from the
same repository and record the substitution in the results table.

- [ ] **Step 4: Write the implementation**

`backend/benchmarks/__init__.py`: empty file.

`backend/benchmarks/bench_pr.py`:

```python
"""Replays a fixed corpus of pull requests and reports the speedup.

Three separate comparisons are reported rather than one number, because a
single figure invites "against what?" and a vague answer reads as inflation.
Publishing the stricter figure next to the headline is what makes the
headline credible.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services import github_app, parse_cache, pr_report, repo_cache  # noqa: E402

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
    index = max(0, min(len(ordered) - 1, int(round(p / 100 * len(ordered) + 0.5)) - 1))
    return ordered[index]


def _reduction(baseline: List[float], improved: List[float]) -> float:
    base = percentile(baseline, 50)
    if base <= 0:
        return 0.0
    return round((base - percentile(improved, 50)) / base * 100, 1)


def summarize(cold: List[float], warm: List[float], full: List[float], incremental: List[float]) -> Dict:
    return {
        "samples": {"cold": len(cold), "warm": len(warm), "full": len(full), "incremental": len(incremental)},
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
        f"{summary['full_parse_p50_ms']:.0f} ms | {summary['incremental_parse_p50_ms']:.0f} ms | "
        f"{summary['full_vs_incremental_reduction_pct']}% |",
        "",
        f"End-to-end warm p95: {summary['warm_p95_ms']:.0f} ms · "
        f"cold p95: {summary['cold_p95_ms']:.0f} ms · "
        f"samples: {summary['samples']}",
    ]
    return "\n".join(lines)


def _run_once(entry: Dict, cold: bool) -> Dict:
    full_name = "/".join(entry["repo_url"].rstrip("/").removesuffix(".git").split("/")[-2:])
    key = repo_cache.project_key(full_name)

    if cold:
        parse_cache.clear(key)
        target = repo_cache.STORAGE_ROOT / key
        if target.exists():
            import shutil

            shutil.rmtree(target, onerror=repo_cache._remove_readonly)

    details = github_app.pull_request(full_name, entry["pr_number"], token=None)
    impact = pr_report.analyze_pr(
        full_name,
        entry["pr_number"],
        details["head"]["sha"],
        details["head"]["repo"]["clone_url"],
        token=None,
    )
    return impact.stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark PR impact analysis")
    parser.add_argument("--repeats", type=int, default=3, help="warm runs per corpus entry")
    parser.add_argument("--corpus", type=Path, default=CORPUS_PATH)
    args = parser.parse_args()

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    cold, warm, full, incremental = [], [], [], []

    for entry in corpus:
        print(f"cold: {entry['repo_url']}#{entry['pr_number']}")
        stats = _run_once(entry, cold=True)
        cold.append(stats["total_ms"])
        # The cold run parsed every file, so its parse stage *is* the
        # full-reparse baseline for this repository.
        full.append(_last_stage_ms("parse_ms"))

        for _ in range(args.repeats):
            print(f"warm: {entry['repo_url']}#{entry['pr_number']}")
            stats = _run_once(entry, cold=False)
            warm.append(stats["total_ms"])
            incremental.append(_last_stage_ms("parse_ms"))

    summary = summarize(cold, warm, full, incremental)
    print()
    print(render_table(summary))


def _last_stage_ms(field: str) -> float:
    """Reads the most recent metrics record's stage duration."""
    from services import metrics

    if not metrics.METRICS_PATH.exists():
        return 0.0
    last = metrics.METRICS_PATH.read_text(encoding="utf-8").strip().splitlines()[-1]
    return json.loads(last).get(field, 0.0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run the tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_bench_pr.py -v
```

Expected: 7 passed.

- [ ] **Step 6: Run the real benchmark**

```bash
.venv/Scripts/python.exe -m benchmarks.bench_pr --repeats 3
```

This one command **does** use the network — it is not part of the test suite.
Expect several minutes on the cold runs.

**Record the printed table verbatim.** It is the source for every number in
the documentation. Do not round it up, and do not quote a figure this table
did not produce.

- [ ] **Step 7: Commit**

```bash
git add backend/benchmarks backend/tests/test_bench_pr.py
git commit -m "feat: benchmark harness comparing cold, warm, and incremental runs"
```

---

### Task 10: Documentation and configuration

The explanatory document, carrying the full reasoning — not just setup steps.

**Files:**
- Create: `docs/GITHUB_APP_INTEGRATION.md`
- Modify: `backend/.env.example`, `render.yaml`, `README.md`

**Interfaces:**
- Consumes: the benchmark table from Task 9
- Produces: nothing consumed by code

- [ ] **Step 1: Add the environment variables**

Append to `backend/.env.example`:

```
# --- GitHub App integration (automated PR impact analysis) ---
# From the App's settings page. The private key is the full PEM contents;
# if your host mangles newlines, literal "\n" sequences are accepted.
GITHUB_APP_ID=
GITHUB_APP_PRIVATE_KEY=
GITHUB_WEBHOOK_SECRET=

# Optional: a classic token raises the rate limit for the manual
# POST /api/pr/analyze endpoint. Not used by the webhook path.
GITHUB_TOKEN=

# Where clones and the parse-cache index live. Point this at a mounted
# volume in production — the cache is what makes the warm path fast.
CACHE_DIR=

# LLM review per pull request. Off by default: it is slow and costs money
# per event.
PR_AI_REVIEW=off
```

Append to `render.yaml` under `envVars`:

```yaml
      - key: GITHUB_APP_ID
        sync: false
      - key: GITHUB_APP_PRIVATE_KEY
        sync: false
      - key: GITHUB_WEBHOOK_SECRET
        sync: false
      - key: PR_AI_REVIEW
        value: "off"
```

- [ ] **Step 2: Write the documentation**

Create `docs/GITHUB_APP_INTEGRATION.md` with these sections, in this order:

1. **What this does** — one paragraph, plus a lifecycle diagram from webhook delivery to posted comment.
2. **Module map** — the table from this plan's File Structure, one line of "why it exists" per module.
3. **The three layers of caching** — clone reuse, content-hash parse cache, resolver indexes; what each saves and why.
4. **The correctness trap** — copy Decision 1 from the spec in full. This is the most interesting thing in the project; do not abbreviate it.
5. **Design decisions** — copy Decisions 2 through 7 from the spec, each with its rejected alternatives and costs.
6. **Setup** — registering the App (permissions: Contents `read`, Pull requests `write`, Checks `write`; events: Pull request), generating the private key, setting the webhook URL and secret, every environment variable and what it does.
7. **Local development** — how to use `POST /api/pr/analyze` without a public URL, with a `curl` example.
8. **Measured results** — the table from Task 9 **verbatim**, the corpus, the machine it ran on, and a plain statement of which baseline each figure is against.
9. **Deployment caveat** — Render's free plan has no persistent disk and idles down, so a cold start discards the cache and the deployed steady state will not match the benchmark. Production wants a persistent volume.
10. **Known limits** — no cache eviction; per-process graph state; Python only; call resolution is name-based, hence `possible` confidence.
11. **Interview Q&A** — copy the section from the spec verbatim, filling both speed figures from the measured table.
12. **Topics to study** — GitHub App auth (JWT → installation token) vs PATs; HMAC signature verification and replay defense; at-least-once delivery and idempotency; content-addressed caching and invalidation; why incremental computation is hard when name resolution is global; AST static analysis; BFS over reversed edges; background tasks vs job queues; benchmarking methodology, warm vs cold, percentiles vs means.

Every numeric claim must trace to the Task 9 table. If a number is not in that table, it does not go in this document.

- [ ] **Step 3: Link it from the README**

In `README.md`, at the end of the Features list, add:

```markdown
* **Automated PR analysis** — a GitHub App comments the blast radius on every pull request, re-analyzing incrementally so repeat runs reuse the clone and skip unchanged files. See [GitHub App integration](docs/GITHUB_APP_INTEGRATION.md).
```

- [ ] **Step 4: Verify the full suite one last time**

```bash
.venv/Scripts/python.exe -m pytest -v
```

Expected: 67 passed.

- [ ] **Step 5: Verify the app still boots**

```bash
.venv/Scripts/python.exe -c "from main import app; print([r.path for r in app.routes])"
```

Expected: the list includes `/api/github/webhook`, `/api/pr/analyze`, and all pre-existing `/api/project/...` routes.

- [ ] **Step 6: Commit**

```bash
git add docs/GITHUB_APP_INTEGRATION.md backend/.env.example render.yaml README.md
git commit -m "docs: explain the GitHub App integration, decisions, and measurements"
```

---

## Self-Review

**Spec coverage:** Decision 1 → Tasks 2 and 7 (rebuild, documented in both docstrings). Decision 2 → Task 3. Decision 3 → Task 4. Decision 4 → Task 2. Decision 5 → Task 8. Decision 6 → Task 8 (`/api/pr/analyze`). Decision 7 → Task 6 (`upsert_comment`, `post_check_run`). Error handling table → Task 8 (`handle_pull_request`, 401/503/duplicate) and Task 3 (`RepoCacheError`). Testing section → every task. Measurement → Task 9. Configuration → Task 10. Documentation → Task 10.

**Gaps found and closed:** the spec's `PR_AI_REVIEW` flag is declared in configuration but no task consumes it — by design, since AI-per-PR is a non-goal for this iteration. Task 10 documents it as a reserved, currently inert setting rather than pretending it is wired.

**Type consistency:** `project_key` returns a 16-char string used identically by `repo_cache`, `parse_cache`, and `bench_pr`. `CacheStats.hits/misses/deleted/total/hit_ratio` are consumed by `pr_report` and reported by `bench_pr`. `PRImpact` field names match between Task 7's definition, Task 8's response serialization, and Task 8's test fixture. `build_graph_from_metadata` is defined in Task 2 and consumed in Task 7. `metrics.RunMetrics.stage/set/write` are defined in Task 1 and used in Task 7.

**Known caveat carried into execution:** the expected test counts in Tasks 7, 8, and 10 assume every prior task's tests pass unchanged. If a count differs, reconcile before continuing rather than adjusting the expectation.
