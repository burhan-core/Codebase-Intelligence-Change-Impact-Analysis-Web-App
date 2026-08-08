import json
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
