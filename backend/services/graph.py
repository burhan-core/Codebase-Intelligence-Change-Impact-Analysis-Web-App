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

    def toJson(self):
        return nx.node_link_data(self.graph)

# --- Builder Logic ---

def build_graph(project_id: str) -> DependencyGraph:
    """
    Constructs the dependency graph from computed metadata.
    """
    metadata_path = get_metadata_path(project_id)
    dg = DependencyGraph()

    if not metadata_path.exists():
        return dg

    # 1. First Pass: Create all Nodes (Files & Functions)
    # We need to know all available functions to resolve calls later.
    discovered_functions = set() # Store qualified names
    
    # We'll traverse the metadata directory structure
    for meta_file in metadata_path.rglob("*.py.json"):
        with open(meta_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        file_path = data.get("relative_path", data.get("file_path", ""))
        # Normalized path separator
        file_path = file_path.replace("\\", "/")
        
        # Add File Node
        dg.add_file(file_path)
        
        # Add Function Nodes
        for func in data.get("functions", []):
            # Prefer full_name if available (Phase 2 parser produces this)
            # Fallback to name if not.
            # Ideally, we construct a globally unique ID: filepath::function_name?
            # Or just Qualified Name if unique enough? 
            # Given Python, module.function is usually unique.
            # Let's use: relative_file_path::function_name to be safe against duplicate class names in diff files.
            
            func_name = func.get("full_name", func.get("name"))
            unique_id = f"{file_path}::{func_name}"
            
            dg.add_function(unique_id, file_path, func.get("lineno", 0))
            discovered_functions.add(unique_id)
            
            # Edge: File CONTAINS Function
            dg.add_dependency(file_path, unique_id, "contains")

            # Store the simple name -> unique_id mapping for this file
            # This helps resolve local calls
            # (In a real engine, we'd need a symbol table scope, but this is MVP)

    # 2. Second Pass: Create Edges (Imports & Calls)
    for meta_file in metadata_path.rglob("*.py.json"):
        with open(meta_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        file_path = data.get("relative_path", "").replace("\\", "/")
        
        # --- Handle Imports ---
        for imp in data.get("imports", []):
            # Try to map 'module.name' to a file path
            # This is hard without a full python path resolver.
            # For MVP, we look for files that end with the module name.
            # e.g. "services.ingestion" -> match "backend/services/ingestion.py"
            
            module_name = imp.get("module", "")
            if not module_name: continue
            
            # Heuristic: convert dots to slashes
            expected_suffix = module_name.replace(".", "/") + ".py"
            
            # Search existing file nodes for a match
            # This is O(N) per import, optimization needed for huge repos
            for node_id in dg.graph.nodes:
                node = dg.graph.nodes[node_id]
                if node["type"] == "file" and node_id.endswith(expected_suffix):
                    dg.add_dependency(file_path, node_id, "imports")
                    break

        # --- Handle Calls ---
        for func in data.get("functions", []):
            caller_name = func.get("full_name", func.get("name"))
            caller_id = f"{file_path}::{caller_name}"
            
            for call in func.get("calls", []):
                callee_name = call.get("name")
                
                # Resolution Strategy:
                # 1. Check local file (is it defined in this file?)
                local_callee_id = f"{file_path}::{callee_name}"
                if local_callee_id in discovered_functions:
                    dg.add_dependency(caller_id, local_callee_id, "calls")
                    continue
                
                # 2. Check imported files
                # If we found import edges, check those files for the function.
                # (Complex for MVP, let's try a global search if name is unique enough)
                
                # 3. Global Fallback (Loose matching)
                # If 'callee_name' exists in any other file, link it.
                # This may produce false positives (e.g. two files have 'init'), 
                # but better than missing edges for "Dependency Graph".
                
                # Optimization: Only search if not found locally
                match_found = False
                potential_matches = []
                
                for potential_id in discovered_functions:
                    # Potential ID format: path::Qualified.Name
                    # Check if it ends with ::callee_name
                    if potential_id.endswith(f"::{callee_name}"):
                        potential_matches.append(potential_id)
                
                if len(potential_matches) == 1:
                    # High confidence match
                    dg.add_dependency(caller_id, potential_matches[0], "calls")
                elif len(potential_matches) > 1:
                    # Ambiguous. Link all? Or link none? 
                    # For "Impact Analysis", false positives (linking all) is safer than false negatives.
                    # Warning: This makes the graph "noisy".
                    for match in potential_matches:
                        dg.add_dependency(caller_id, match, "calls_ambiguous")

    return dg
