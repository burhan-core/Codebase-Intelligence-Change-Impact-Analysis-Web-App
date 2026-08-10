import json
import networkx as nx
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple
from services.analysis import get_metadata_path, get_project_path

# --- Node Definitions ---

class Node:
    def __init__(self, id: str, type: str, **kwargs):
        self.id = id
        self.type = type
        self.attributes = kwargs

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            **self.attributes
        }

class FileNode(Node):
    def __init__(self, path: str):
        super().__init__(id=path, type="file", label=Path(path).name)

class FunctionNode(Node):
    def __init__(self, qualified_name: str, file_path: str, lineno: int):
        super().__init__(
            id=qualified_name, 
            type="function", 
            file_path=file_path, 
            lineno=lineno,
            label=qualified_name.split('.')[-1]
        )

# --- Graph Engine ---

class DependencyGraph:
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_file(self, path: str):
        node = FileNode(path)
        self.graph.add_node(node.id, **node.to_dict())

    def add_function(self, qualified_name: str, file_path: str, lineno: int):
        node = FunctionNode(qualified_name, file_path, lineno)
        self.graph.add_node(node.id, **node.to_dict())

    def add_dependency(self, source_id: str, target_id: str, type: str):
        """
        Adds a directed edge from source to target.
        Types: 'imports', 'calls', 'contains'
        """
        self.graph.add_edge(source_id, target_id, type=type)

    def get_node(self, node_id: str):
        if self.graph.has_node(node_id):
            return self.graph.nodes[node_id]
        return None

    def get_callers(self, node_id: str) -> List[Dict]:
        """Returns list of nodes that call/import this node."""
        if not self.graph.has_node(node_id):
            return []
        
        predecessors = self.graph.predecessors(node_id)
        return [self.graph.nodes[p] for p in predecessors]

    def get_callees(self, node_id: str) -> List[Dict]:
        """Returns list of nodes that this node calls/imports."""
        if not self.graph.has_node(node_id):
            return []
            
        successors = self.graph.successors(node_id)
        return [self.graph.nodes[s] for s in successors]

    def get_impact(self, node_id: str, max_depth: int = 25) -> Optional[List[Dict]]:
        """
        Computes the blast radius of changing `node_id`: every node that
        transitively depends on it, via BFS over *incoming* edges.

        'contains' edges are skipped (a file trivially contains its own
        functions). Confidence degrades to 'possible' once any hop on the
        path was an ambiguous call match.
        """
        if not self.graph.has_node(node_id):
            return None

        visited = {node_id}
        queue = [(node_id, 0, False)]
        results = []

        while queue:
            current, depth, ambiguous = queue.pop(0)
            if depth >= max_depth:
                continue

            for pred in self.graph.predecessors(current):
                edge_type = self.graph.edges[pred, current].get("type")
                if edge_type == "contains" or pred in visited:
                    continue

                visited.add(pred)
                is_ambiguous = ambiguous or edge_type == "calls_ambiguous"

                entry = dict(self.graph.nodes[pred])
                entry["depth"] = depth + 1
                entry["confidence"] = "possible" if is_ambiguous else "direct"
                entry["via"] = edge_type
                results.append(entry)

                queue.append((pred, depth + 1, is_ambiguous))

        return results

    def toJson(self):
        return nx.node_link_data(self.graph)

# --- Builder Logic ---

def _load_metadata_documents(metadata_path: Path) -> List[Tuple[str, Dict]]:
    """Reads every metadata JSON once. The original builder read each file
    twice (once per pass); reading once and reusing halves the disk I/O."""
    documents = []
    for meta_file in metadata_path.rglob("*.py.json"):
        with open(meta_file, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        file_path = data.get("relative_path", data.get("file_path", ""))
        documents.append((file_path.replace("\\", "/"), data))
    return documents


def _resolve_import_target(module_name: str, file_index: Dict[str, str]) -> Optional[str]:
    """Maps a module name to a file node id via the prebuilt index.

    The original scanned every file node per import. `file_index` maps both
    'a/b.py' and 'a/b/__init__.py' shapes plus each of their path suffixes,
    so resolution is a dict lookup with the same matching semantics:
    exact id, or a match on a '/'-delimited path boundary.
    """
    module_path = module_name.replace(".", "/")
    for candidate in (f"{module_path}.py", f"{module_path}/__init__.py"):
        target = file_index.get(candidate)
        if target is not None:
            return target
    return None


def build_graph_from_metadata(metadata_path: Path) -> DependencyGraph:
    """Constructs the dependency graph from computed metadata.

    Call resolution here is *global*: a callee name is matched against every
    known function in the repository. That is why the graph is rebuilt in
    full on every analysis rather than patched per changed file — adding a
    function anywhere can flip call sites in files that did not change.
    See Decision 1 in the design spec.
    """
    dg = DependencyGraph()

    if not metadata_path.exists():
        return dg

    documents = _load_metadata_documents(metadata_path)

    # --- Pass 1: nodes, plus the indexes that make pass 2 linear ---
    # name -> [function ids], for call resolution.
    name_index: Dict[str, List[str]] = {}
    # candidate path -> file node id, for import resolution.
    file_index: Dict[str, str] = {}
    discovered_functions = set()

    for file_path, data in documents:
        dg.add_file(file_path)

        # Register every '/'-delimited suffix so `endswith("/" + candidate)`
        # becomes a lookup. `setdefault` keeps the first registration, and
        # an exact id is registered by its own full path.
        segments = file_path.split("/")
        for start in range(len(segments)):
            file_index.setdefault("/".join(segments[start:]), file_path)

        for func in data.get("functions", []):
            func_name = func.get("full_name", func.get("name"))
            unique_id = f"{file_path}::{func_name}"

            dg.add_function(unique_id, file_path, func.get("lineno", 0))
            discovered_functions.add(unique_id)
            dg.add_dependency(file_path, unique_id, "contains")

            # A call site writes `save_user` or `Class.method`; index the
            # trailing segment after '::' exactly as the original matched it.
            name_index.setdefault(func_name, []).append(unique_id)

    # --- Pass 2: edges ---
    for file_path, data in documents:
        for imp in data.get("imports", []):
            module_name = imp.get("from_module") or imp.get("module", "")
            if not module_name:
                continue
            target = _resolve_import_target(module_name, file_index)
            if target is not None:
                dg.add_dependency(file_path, target, "imports")

        for func in data.get("functions", []):
            caller_name = func.get("full_name", func.get("name"))
            caller_id = f"{file_path}::{caller_name}"

            for call in func.get("calls", []):
                callee_name = call.get("name")

                local_callee_id = f"{file_path}::{callee_name}"
                if local_callee_id in discovered_functions:
                    dg.add_dependency(caller_id, local_callee_id, "calls")
                    continue

                matches = name_index.get(callee_name, [])
                if len(matches) == 1:
                    dg.add_dependency(caller_id, matches[0], "calls")
                elif len(matches) > 1:
                    # False positives are safer than false negatives for a
                    # blast-radius tool, so link all candidates but mark them.
                    for match in matches:
                        dg.add_dependency(caller_id, match, "calls_ambiguous")

    return dg


def build_graph(project_id: str) -> DependencyGraph:
    """Constructs the dependency graph for a project id."""
    return build_graph_from_metadata(get_metadata_path(project_id))


