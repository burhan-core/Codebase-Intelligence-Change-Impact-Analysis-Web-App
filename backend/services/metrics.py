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
