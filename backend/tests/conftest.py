import sys
from pathlib import Path

# Tests import `services.*` the same way the app does, so the backend
# directory must be on sys.path regardless of where pytest was invoked.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
