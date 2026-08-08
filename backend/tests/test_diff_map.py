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
