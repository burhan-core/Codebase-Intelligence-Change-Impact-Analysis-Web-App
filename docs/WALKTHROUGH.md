# Impact Lens — Full Walkthrough

This document explains how the app works end to end, what was changed in the July 2026 overhaul and why, and how to present the project in an interview.

---

## 1. What the app does, in one paragraph

You paste a GitHub/GitLab URL. The backend clones the repository, parses every Python file into an AST, and builds a directed dependency graph connecting files and functions. The frontend gives you an IDE-style workspace to browse the code, and — the core feature — lets you target any function and see its **blast radius**: every function that would be affected if you changed it, at any depth, grouped by file. Nothing is ever executed; every result is derived from parsing source code.

---

## 2. The request flow, function by function

### Step 1 — Ingest (user clicks "Analyze")

```
RepoInputForm.handleSubmit()              [src/components/ui/RepoInputForm.jsx]
  └─▶ api.ingest(url)                     [src/lib/api.js]
        └─▶ POST /api/ingest              [backend/main.py → ingest_repository()]
              ├─▶ clone_repository(url)   [backend/services/ingestion.py]
              │     • generates a uuid4 project_id
              │     • git shallow-clone (depth=1) into backend/storage/<project_id>/
              └─▶ scan_directory(path)    [backend/services/scanner.py]
                    • walks the clone, returns a nested file-tree JSON
```

The response `{ project_id, file_tree }` is passed to the workspace via React Router navigation state. The `project_id` is the handle for every later request.

### Step 2 — Parse (automatic, on workspace mount)

```
OverviewPage useEffect                    [src/pages/OverviewPage.jsx]
  └─▶ api.parseProject(projectId)
        └─▶ POST /api/project/{id}/parse  [backend/main.py → trigger_parse()]
              └─▶ parse_project(id)       [backend/services/analysis.py]
                    for every *.py file:
                    └─▶ parse_file()      [backend/services/parser.py]
                          • ast.parse() the source
                          • CodeParser(ast.NodeVisitor) walks the tree:
                            - visit_Import / visit_ImportFrom → imports list
                            - visit_ClassDef → classes (+ methods)
                            - visit_FunctionDef → functions (name, line, args)
                            - visit_Call → records every call made inside a function
                          • result saved to metadata/<id>/<path>.py.json
```

One JSON metadata file per source file. The status bar shows "N files indexed" from this response.

### Step 3 — Explore (user clicks files)

* File content: `GET /api/project/{id}/file?path=…` reads the file from the clone (with a path-traversal guard that rejects paths outside the project root) and Monaco renders it read-only.
* Symbols: `GET /api/project/{id}/metadata?path=…` returns that file's parsed JSON; the Symbols tab lists classes, methods, and functions with jump-to-line.

### Step 4 — Graph (lazy, first dependency/impact request)

```
build_graph(project_id)                   [backend/services/graph.py]
  Pass 1 — nodes:
    • FileNode  (id = relative path)
    • FunctionNode (id = "path::Qualified.Name")
    • edge file ──contains──▶ function
  Pass 2 — edges:
    • imports: "services.ingestion" → find file ending "services/ingestion.py"
    • calls: for each call recorded by the parser, resolve the callee:
        1. same file?           → edge (calls)
        2. unique global match? → edge (calls)
        3. multiple matches?    → edges to all (calls_ambiguous)
```

The graph is a `networkx.DiGraph` cached in memory per project (`GRAPH_CACHE`).

### Step 5 — Impact (user clicks the crosshair on a function)

```
StructurePanel crosshair → OverviewPage.handleTargetImpact() → ImpactPanel
  └─▶ api.getImpact(projectId, nodeId)
        └─▶ GET /api/project/{id}/impact?node_id=…   [backend/main.py → get_impact()]
              └─▶ DependencyGraph.get_impact()        [backend/services/graph.py]
                    breadth-first search over INCOMING edges:
                    • start at the target node, depth 0
                    • each predecessor = something that calls/imports it
                    • record depth (1 = direct caller, 2 = caller-of-caller…)
                    • confidence: 'direct' unless any hop was calls_ambiguous
                    • 'contains' edges skipped, visited-set prevents cycles
```

Why *incoming* edges: an edge `A ──calls──▶ B` means A depends on B. So "what breaks if I change B?" is answered by walking edges backwards from B. BFS (not DFS) is used so `depth` is the *shortest* dependency distance — the honest "how directly am I affected" number. The visited set makes it O(V+E) and safe on recursive/cyclic call graphs.

The response includes a summary (total affected, files touched, max depth, direct callers) that the ImpactPanel renders as stat tiles, and the full node list grouped by file with `d1/d2…` depth badges — every row clickable to jump to that caller's source line.

---

## 3. What was changed in the overhaul, and why

### Repo hygiene
* **Removed ~2,700 committed artifacts** (`backend/metadata/`, `backend/backend/`, `__pycache__/`) — runtime output of previously analyzed repos had been committed, drowning the actual source. `.gitignore` now excludes `storage/`, `metadata/`, caches, and `.env`.
* **`networkx` added to `requirements.txt`** — it was imported by `graph.py` but never declared, so a fresh install crashed.
* **README rewritten** — real setup instructions (it had none), an honest feature list, and the architecture diagram above.

### Bug fixes
* **Rules-of-Hooks violation** (`OverviewPage.jsx`): the component returned `null` *before* two `useEffect` hooks. React requires the same hooks in the same order on every render; an early return changes the hook count and corrupts state. All hooks now run before the guard.
* **Fake ZIP drop-zone removed**: it rendered but did nothing on drop. Dead UI erodes trust; deletion beat implementing an upload path nobody asked for.
* **Real URL validation**: `url.includes('github.com')` accepted almost anything; it's now a regex for `https://(github|gitlab).com/owner/repo` with inline feedback.
* **API base URL** is `import.meta.env.VITE_API_BASE_URL` with a localhost fallback instead of a hardcoded constant.
* **Non-Python files** now show an explicit "only .py files are analyzed" notice instead of a silently empty panel.

### The impact engine (new)
The project's name promised change-impact analysis, but the backend could only answer "who directly calls X?" — a one-hop lookup. The new `get_impact()` BFS (about 30 lines) plus the `/impact` endpoint make the transitive blast-radius query real, with depth and confidence per result. The ImpactPanel is the UI for it.

### UI redesign
* **One design system**: the old app mixed a blue/slate landing page with an indigo-on-`#030014` glow-gradient workspace. Now: zinc-950 surfaces, zinc-800 borders, a single blue accent, amber reserved for impact/risk semantics, Inter for UI, JetBrains Mono for anything code-like.
* **Rebrand**: RepoSpy → **Impact Lens**, consistent across navbar, page title, favicon (a lens/crosshair SVG), and README.
* **Landing page**: gradient-card template look replaced with a developer-tool hero (plus a static mock "impact report" so visitors see the product immediately), a four-step how-it-works strip, and honest does/doesn't columns.
* **Workspace**: three-pane IDE layout with a tabbed right rail (Symbols / Impact), selected-file highlight and folders-first sorting in the tree, language-aware icons, a custom Monaco theme matched to the background, and a status bar showing indexing progress and parse errors.

---

## 4. Explaining it to a recruiter (the 90-second version)

> "Impact Lens answers the question every engineer asks before touching shared code: *what breaks if I change this?*
>
> When you give it a repository URL, a FastAPI backend shallow-clones it and runs Python's `ast` module over every file — so nothing is executed, it's pure static analysis. The parser records every function, class, import, and every call each function makes. From that I build a directed graph with networkx: files and functions are nodes, and 'imports' and 'calls' are edges.
>
> The key feature is impact analysis. An edge A→B means A depends on B, so to find the blast radius of changing B I run a breadth-first search over the *incoming* edges from B. BFS gives me the shortest dependency distance, so every affected function gets an honest depth — direct caller, caller-of-caller, and so on. Static call resolution in Python is undecidable in general, so when a name matches more than one function I keep all candidates but mark them lower-confidence — for impact analysis a false positive is safer than a missed dependency.
>
> The frontend is React with a Monaco-based read-only IDE: file tree, code viewer, and a symbol panel where you target any function with one click and get the full blast radius grouped by file, each result jumping straight to the caller's source line."

**Questions you should expect, with answers:**

* *Why BFS and not DFS?* — BFS visits nodes in order of distance, so the first time I reach a node its depth is minimal. Depth is the product's core signal ("how directly does this affect me"), so it must be the shortest path.
* *How do you handle cycles (recursive functions)?* — a visited set; each node is reported once at its shallowest depth, and traversal terminates in O(V+E).
* *Why can call resolution be ambiguous?* — Python is dynamic: `obj.save()` could be any of several `save` methods, and there's no type information in a static parse. I resolve same-file names first, then unique global names; multiple matches become `calls_ambiguous` edges surfaced as lower-confidence results rather than dropped.
* *Why not just grep for the function name?* — grep finds text, not structure: it can't distinguish a call from a comment or a same-named method on another class, and it can't give you transitive depth. The AST gives exact, positional, structural facts.
* *What are the limits?* — Python only for now; decorators and dynamic dispatch (`getattr`, callbacks) aren't traced; import resolution uses a path-suffix heuristic rather than a full module resolver. Each is an isolated extension point: the parser, the resolver, and the traversal are separate services.

---

## 5. The graph view (added after the initial overhaul)

The workspace has an **IDE / Graph** toggle (bottom-center pill). Graph mode renders the repository's file-level import structure with React Flow: each Python file is a node, each resolved import a directed edge, laid out left-to-right with dagre. Files with no import relationships are parked in a compact grid below the connected graph. Click a node to load its symbols; double-click to open it in the IDE view. If an impact target is active, every file in its blast radius is tinted amber.

Two real bugs surfaced while building it:

* **Relative imports never resolved.** The old resolver only handled `import x.y` — for `from .core import Argument` the parser stores `module="core.Argument"`, which mapped to the non-existent path `core/Argument.py`. The fix prefers `from_module` when present, matches on path boundaries (so `utils.py` can no longer match `_utils.py`), and also tries `<module>/__init__.py` for packages. On the click repo this took import edges from **0 to 152**.
* **networkx key drift.** Newer networkx emits the edge list under `edges`, not `links`; the frontend now accepts both.

File-level (not function-level) granularity is deliberate: a function-level graph of even a mid-size repo is thousands of nodes — unreadable. Files answer the architectural question; the Impact panel answers the function-level one.

## 6. The AI review layer

Static analysis tells you *what* is connected; the AI layer reasons about *whether the change is safe*. When a function is targeted in the Impact panel, an "AI review" section can send everything the engine knows to an LLM:

```
ImpactPanel → AiInsight → api.askAi()
  └─▶ POST /api/project/{id}/ask            [backend/main.py → ask_ai()]
        ├─▶ dg.get_impact(node_id)           reuse of the BFS blast radius
        ├─▶ llm.build_context()              [backend/services/llm.py]
        │     • the function's actual source (lines from the clone)
        │     • its signature, calls made, async flag (from metadata)
        │     • direct + transitive callers with depth and confidence
        └─▶ llm.ask() → DeepSeek chat completions (OpenAI-compatible)
```

Design decisions worth naming in an interview:

* **The key stays server-side.** `DEEPSEEK_API_KEY` lives in `backend/.env` (gitignored); the browser only calls our own `/ask` endpoint. Shipping an LLM key in frontend code would let anyone extract it from the bundle.
* **The model gets facts, not the whole repo.** Context is the deterministic analysis output — source of one function, its callers with depth — so answers are grounded and cheap. The static engine stays the source of truth; the LLM interprets it.
* **Conversation is stateless on the server.** The frontend keeps the message history and replays it with each request; the server rebuilds the static context every time. No server-side session state to manage.
* **Failure degrades gracefully** — API errors (no key, no balance, timeouts) surface as readable messages in the panel; the rest of the app never depends on the LLM.

## 7. Graph readability model

Hovering or selecting a node answers "what is this connected to" without tracing lines by eye: its **importers** turn amber (they break if it changes), its **imports** turn emerald (what it relies on), incident edges thicken and animate in the matching color, and every unrelated node fades to near-invisible. A card in the corner states both counts in words, and a legend pins the color semantics. Amber/emerald mirror the Impact panel's meaning of amber = affected, so the two views teach the same vocabulary.

## 8. Where to extend next

1. **JavaScript/TypeScript support** — add a parser service producing the same metadata shape (e.g. via tree-sitter); the graph and impact code don't change.
2. **Decorator awareness** — record `decorator_list` in `visit_FunctionDef` as call edges; would make framework-heavy code (Flask/Click/FastAPI) far more connected.
3. **Persistence** — projects live in memory/disk with no index; a small SQLite table of past analyses would enable a "recent projects" screen.
4. **Risk scoring** — the graph already knows in-degrees; "most-depended-on functions" is a cheap, high-value hotspot dashboard.
