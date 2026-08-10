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
