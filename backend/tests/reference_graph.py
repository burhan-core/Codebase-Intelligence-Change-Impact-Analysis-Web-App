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
