import json
import subprocess
import sys
from pathlib import Path

import pytest

# Tests import `services.*` the same way the app does, so the backend
# directory must be on sys.path regardless of where pytest was invoked.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


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
            {
                "name": "save_user",
                "full_name": "save_user",
                "lineno": 3,
                "end_lineno": 9,
                "calls": [{"name": "log", "lineno": 4}],
            },
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
    # `import os` at line 1 gives tests a module-level line that sits outside
    # any function body, so the file-node fallback can be exercised.
    (repo / "app" / "main.py").write_text(
        "import os\n\n\ndef handler():\n    return store_it()\n", encoding="utf-8"
    )
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
