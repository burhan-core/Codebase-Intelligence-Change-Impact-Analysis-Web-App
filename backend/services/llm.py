"""
AI change-impact review via any OpenAI-compatible chat API
(Groq, DeepSeek, OpenAI, ...). Configure in backend/.env:

    LLM_API_KEY=...            required
    LLM_BASE_URL=https://api.groq.com/openai/v1     (default)
    LLM_MODEL=llama-3.3-70b-versatile               (default)

The key lives in backend/.env (gitignored) and never reaches the frontend;
the browser talks only to our /ask endpoint.
"""
import os
import json
import requests
from pathlib import Path
from typing import Dict, List, Optional

from services.ingestion import get_project_path
from services.analysis import get_file_metadata

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env():
    """Tiny .env loader — avoids a python-dotenv dependency."""
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_env()

SYSTEM_PROMPT = """You are a senior software engineer performing a change-impact review.
You are given static-analysis facts about one Python function in a repository:
its source code, what it calls, and its blast radius (every caller, direct and
transitive, with dependency depth — depth 1 = calls it directly).

When asked for an assessment, cover concisely:
1. Risk level of changing this function (low/medium/high) and why, grounded in
   the caller list — how many callers, how central, which files.
2. What is safe to change (internals that don't leak) vs. what is dangerous
   (signature, return shape, raised exceptions, side effects callers rely on).
3. Security notes if the code touches input parsing, paths, subprocess,
   network, auth, or serialization — otherwise say there is no obvious
   security-sensitive surface.
4. A short checklist of what to verify before shipping a change.

Reference concrete caller/file names from the data. If the data is too thin to
be sure, say so instead of inventing certainty. Answer in plain text (no
markdown headers or tables; simple dashes for lists are fine). Keep it tight —
under ~350 words unless the user asks for more."""


def _read_function_source(project_id: str, file_path: str, lineno: int, end_lineno: int, max_lines: int = 120) -> str:
    try:
        full = get_project_path(project_id) / file_path
        lines = full.read_text(encoding="utf-8", errors="replace").splitlines()
        snippet = lines[max(0, lineno - 1): min(len(lines), end_lineno)]
        if len(snippet) > max_lines:
            snippet = snippet[:max_lines] + ["# ... truncated ..."]
        return "\n".join(snippet)
    except Exception:
        return "(source unavailable)"


def build_context(project_id: str, node_id: str, node: Dict, impact: List[Dict]) -> str:
    """Assemble the static-analysis facts the model reasons over."""
    file_path = node.get("file_path", "")
    label = node.get("label", node_id)

    # Function detail (args, calls, spans) from the file's metadata
    func_detail = None
    meta = get_file_metadata(project_id, file_path) if file_path else None
    if meta:
        wanted = node_id.split("::")[-1]
        for f in meta.get("functions", []):
            if f.get("full_name", f.get("name")) == wanted:
                func_detail = f
                break

    source = ""
    if func_detail:
        source = _read_function_source(
            project_id, file_path, func_detail["lineno"], func_detail.get("end_lineno", func_detail["lineno"] + 40)
        )

    callers = [
        {"name": n.get("label", n["id"]), "file": n.get("file_path", n["id"]),
         "depth": n["depth"], "confidence": n["confidence"]}
        for n in impact[:60]
    ]
    files_affected = sorted({c["file"] for c in callers})

    context = {
        "function": label,
        "defined_in": file_path,
        "signature_args": func_detail.get("args", []) if func_detail else [],
        "is_async": func_detail.get("is_async", False) if func_detail else False,
        "calls_made": [c["name"] for c in (func_detail or {}).get("calls", [])][:40],
        "blast_radius": {
            "total_affected_symbols": len(impact),
            "files_affected": files_affected,
            "direct_callers": [c for c in callers if c["depth"] == 1],
            "transitive_callers": [c for c in callers if c["depth"] > 1],
        },
    }

    parts = ["STATIC ANALYSIS DATA:", json.dumps(context, indent=1)]
    if source:
        parts += ["", f"SOURCE OF {label} ({file_path}):", "```python", source, "```"]
    return "\n".join(parts)


def ask(context: str, question: Optional[str], history: Optional[List[Dict]]) -> str:
    # DEEPSEEK_* accepted as legacy fallbacks
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL") or os.environ.get("DEEPSEEK_BASE_URL") or "https://api.groq.com/openai/v1"
    model = os.environ.get("LLM_MODEL") or os.environ.get("DEEPSEEK_MODEL") or "llama-3.3-70b-versatile"
    if not api_key:
        raise RuntimeError("LLM_API_KEY is not configured. Add it to backend/.env")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": context},
        {"role": "assistant", "content": "Understood. I have reviewed the static-analysis data for this function."},
    ]
    for m in history or []:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({
        "role": "user",
        "content": question or "Give me the change-impact assessment for this function.",
    })

    resp = requests.post(
        base_url.rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "temperature": 0.3, "max_tokens": 1200},
        timeout=90,
    )
    data = resp.json()
    if resp.status_code != 200:
        detail = data.get("error", {}).get("message", resp.text[:200])
        raise RuntimeError(f"LLM API error: {detail}")
    return data["choices"][0]["message"]["content"]
