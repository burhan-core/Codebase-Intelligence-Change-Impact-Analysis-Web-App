import ast
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

class CodeParser(ast.NodeVisitor):
    def __init__(self, file_content: str, file_path: str):
        self.file_path = file_path
        self.lines = file_content.splitlines()
        self.imports = []
        self.classes = []
        self.functions = []
        
        # Context tracking
        self.current_class = None
        self.current_function = None
        self.function_stack = [] # Stack of (name, start_line)

    def parse(self):
        tree = ast.parse("\n".join(self.lines))
        self.visit(tree)
        return {
            "file_path": self.file_path,
            "imports": self.imports,
            "classes": self.classes,
            "functions": self.functions
        }

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append({
                "module": alias.name,
                "alias": alias.asname,
                "lineno": node.lineno
            })
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module or ""
        for alias in node.names:
            self.imports.append({
                "module": f"{module}.{alias.name}" if module else alias.name,
                "alias": alias.asname,
                "lineno": node.lineno,
                "from_module": module
            })
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        class_info = {
            "name": node.name,
            "lineno": node.lineno,
            "end_lineno": node.end_lineno,
            "methods": [],
            "bases": [self._get_name(b) for b in node.bases]
        }
        
        self.classes.append(class_info)
        
        # Push context
        prev_class = self.current_class
        self.current_class = class_info
        
        self.generic_visit(node)
        
        # Pop context
        self.current_class = prev_class

    def visit_FunctionDef(self, node):
        self._handle_function(node)

    def visit_AsyncFunctionDef(self, node):
        self._handle_function(node, is_async=True)

    def _handle_function(self, node, is_async=False):
        func_name = node.name
        
        # Determine strict parent name (Class.Method or Function.LocalFunction)
        parent_name = None
        if self.current_class:
            parent_name = self.current_class["name"]
        elif self.function_stack:
            parent_name = self.function_stack[-1]["name"]

        full_name = f"{parent_name}.{func_name}" if parent_name else func_name

        func_info = {
            "name": func_name,
            "full_name": full_name,
            "lineno": node.lineno,
            "end_lineno": node.end_lineno,
            "args": [arg.arg for arg in node.args.args],
            "calls": [],
            "is_async": is_async,
            "parent": parent_name
        }

        # If we are inside a class, add to class methods, otherwise global functions
        # Note: We also add methods to the global functions list for easy searching, 
        # but mark them with 'parent'. Or we can keep them separate. 
        # The user asked for "List all functions in this repo", so a flat list + class nesting is good.
        
        self.functions.append(func_info)
        if self.current_class:
            self.current_class["methods"].append(func_info)

        # Push context
        self.function_stack.append(func_info)
        
        self.generic_visit(node)
        
        # Pop context
        self.function_stack.pop()

    def visit_Call(self, node):
        # We only care about calls inside functions
        if not self.function_stack:
            return

        current_func = self.function_stack[-1]
        
        # Extract callee name
        callee_name = self._get_name(node.func)
        
        call_info = {
            "name": callee_name,
            "lineno": node.lineno,
            "args_count": len(node.args)
        }
        
        current_func["calls"].append(call_info)
        
        self.generic_visit(node)

    def _get_name(self, node) -> str:
        """Helper to get string representation of a node (Name, Attribute, etc.)"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Call):
            return "Call(...)" # Dynamic call
        elif isinstance(node, ast.Subscript):
            return f"{self._get_name(node.value)}[]"
        elif isinstance(node, str):
            return node
        return "unknown"

def parse_file(file_path: str, content: str = None) -> Dict:
    path_obj = Path(file_path)
    if content is None:
        try:
             content = path_obj.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            return {"error": str(e), "file_path": file_path}

    parser = CodeParser(content, file_path)
    try:
        return parser.parse()
    except Exception as e:
        return {
            "file_path": file_path,
            "error": f"Parse Error: {str(e)}",
            "imports": [],
            "classes": [],
            "functions": []
        }
