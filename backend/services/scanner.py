import os
from pathlib import Path
from typing import List, Dict, Union

def scan_directory(path: Path) -> List[Dict]:
    """
    Recursively scans a directory and returns a file tree structure 
    compatible with the frontend FileTree component.
    """
    tree = []
    
    try:
        # Sort directories first, then files
        entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
        
        for entry in entries:
            # Skip hidden files/folders (like .git)
            if entry.name.startswith('.'):
                continue
                
            node = {
                "name": entry.name,
                "path": entry.path, # Absolute path (internal use)
                "type": "folder" if entry.is_dir() else "file"
            }
            
            if entry.is_dir():
                node["children"] = scan_directory(Path(entry.path))
            else:
                # Basic language detection by extension
                ext = Path(entry.name).suffix.lower()
                node["language"] = get_language_from_ext(ext)
                
            tree.append(node)
            
    except PermissionError:
        pass # Skip folders we can't access
        
    return tree

def get_language_from_ext(ext: str) -> str:
    mapping = {
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.py': 'python',
        '.html': 'html',
        '.css': 'css',
        '.json': 'json',
        '.md': 'markdown',
        '.java': 'java',
        '.c': 'c',
        '.cpp': 'cpp',
    }
    return mapping.get(ext, 'plaintext')
