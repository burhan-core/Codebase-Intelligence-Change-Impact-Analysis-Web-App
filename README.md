# Impact Lens

> **See what breaks before you change code.**

Impact Lens is a static-analysis web app that maps the dependency structure of a codebase and shows the **blast radius** of changing any function — which callers break, how far the ripple travels, and why. No code is executed, no AI guesswork: every edge in the graph comes from parsing the source.

---

## Interface

<table>
  <tr>
    <td width="50%" align="center" valign="top">
      <img src="https://github.com/user-attachments/assets/30619e81-e7ef-41f4-88d0-f9177b715068" alt="Initial View" width="100%">
      <br>
      <em>Figure 1: Codebase exploration</em>
    </td>
    <td width="50%" align="center" valign="top">
      <img src="https://github.com/user-attachments/assets/f59d4f33-12d6-465d-a13e-b1c64af8d462" alt="Impact View" width="100%">
      <br>
      <em>Figure 2: Change impact paths</em>
    </td>
  </tr>
</table>

---

## Features

* **Repository ingestion** — paste a GitHub/GitLab URL; the backend shallow-clones it into isolated per-project storage.
* **AST parsing** — every Python file is parsed into structured metadata: imports, classes, functions, and the calls each function makes.
* **Dependency graph** — a directed graph (networkx) connects files and functions through `contains`, `imports`, and `calls` edges.
* **Impact analysis** — select any function and traverse the graph *upstream* to find every caller, transitively, with depth and confidence for each hit.
* **IDE-style workspace** — file explorer, read-only Monaco code viewer with jump-to-line, and a symbol map of every class/function in the open file.
* **Graph view** — switch the workspace to an interactive map of the repository's import structure (pan/zoom/minimap). Hover any file to trace its connections: amber = files that import it (break if it changes), emerald = files it depends on; everything else fades out. An active impact target tints its whole blast radius.
* **AI change review** — send a targeted function's source + full blast radius to an LLM (DeepSeek) and ask what's safe to change, what will break, and whether the area is security-sensitive — with follow-up questions in context.

**What it does *not* do:** execute code, generate code, or push changes. Analysis currently covers **Python** sources; other files are browsable but not analyzed.

---

## Architecture

```
React (Vite) ──HTTP──▶ FastAPI
                         │
        ┌────────────────┼─────────────────┐
        ▼                ▼                 ▼
   ingestion.py     analysis.py        graph.py
   git clone into   ast-parse each     build DiGraph from
   storage/<id>/    .py file, write    metadata; traverse
                    metadata/<id>/     callers/callees/impact
```

1. **Ingest** (`POST /api/ingest`) — clones the repo, returns a `project_id` and the file tree.
2. **Parse** (`POST /api/project/{id}/parse`) — walks the clone, runs an `ast.NodeVisitor` over each Python file, and persists one JSON metadata file per source file.
3. **Graph** (`GET /api/project/{id}/dependencies`) — builds a directed graph from the metadata: file nodes, function nodes, and edges for containment, imports, and (resolved) calls.
4. **Impact** (`GET /api/project/{id}/impact?node_id=...`) — breadth-first traversal over *incoming* call edges, returning every transitive caller with its depth and match confidence.

---

## Getting started

### Prerequisites

* Node.js 18+
* Python 3.10+
* Git available on PATH

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
npm install
npm run dev
```

Open http://localhost:5173, paste a repository URL (a Python project — e.g. a Flask or FastAPI repo), and explore.

To point the frontend at a different backend, set `VITE_API_BASE_URL` in a `.env` file.

### AI review (optional)

Works with any OpenAI-compatible chat API (Groq, DeepSeek, OpenAI…). Create `backend/.env` (gitignored; the key never reaches the browser — the frontend only talks to this backend):

```
LLM_API_KEY=gsk_...
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
```

Without a key, everything else works; the AI review section will just report that it isn't configured.

---

## Deployment

Deploys as two pieces: a FastAPI backend on **Render** and a static Vite frontend on **Vercel**.

### Backend (Render)

1. Push this repo to GitHub, then in Render: **New → Blueprint**, point it at the repo. It reads `render.yaml` and creates a Python web service rooted at `backend/`, running `uvicorn main:app --host 0.0.0.0 --port $PORT`.
2. Set the environment variables Render prompts for (all defined but left blank in `render.yaml`):
   * `ALLOWED_ORIGINS` — your Vercel frontend URL (e.g. `https://impact-lens.vercel.app`). Leave unset only for testing; it defaults to `*`.
   * `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` — optional, for the AI review feature (see `backend/.env.example`).
3. Note: Render's free-tier disk is ephemeral — cloned repos and parsed metadata are lost on redeploy/restart. That's fine here since projects are re-ingested on demand; nothing needs to persist between deploys.

Without a Blueprint, create the service manually with the same root directory, build command (`pip install -r requirements.txt`), and start command as above.

### Frontend (Vercel)

1. Import the repo into Vercel. It auto-detects Vite; `vercel.json` at the repo root adds the SPA rewrite React Router needs.
2. Set `VITE_API_BASE_URL` in the Vercel project's environment variables to your Render backend URL (e.g. `https://impact-lens-api.onrender.com`).
3. Deploy. `.vercelignore` keeps the Python backend out of the frontend build upload.

### Local development

Copy `.env.example` → `.env` (frontend) and `backend/.env.example` → `backend/.env` (backend) and fill in as needed; both are gitignored.

---

## Tech stack

| Layer    | Technology |
|----------|------------|
| Frontend | React 19, Vite, Tailwind CSS 4, Monaco Editor, React Flow + dagre, Framer Motion |
| Backend  | Python, FastAPI, GitPython, `ast` (stdlib), networkx |

---

## Project structure

```
├── backend/
│   ├── main.py               # FastAPI app + all API routes
│   └── services/
│       ├── ingestion.py      # git clone into storage/<project_id>
│       ├── scanner.py        # file-tree scan
│       ├── parser.py         # ast.NodeVisitor → per-file metadata
│       ├── analysis.py       # parse orchestration + metadata access
│       └── graph.py          # dependency graph build + impact traversal
└── src/
    ├── pages/                # Landing, Input, Overview (workspace)
    ├── components/ui/        # FileTree, CodeViewer, StructurePanel, ImpactPanel…
    ├── layout/               # Navbar, Layout shell
    └── lib/api.js            # typed fetch wrappers for the API
```
