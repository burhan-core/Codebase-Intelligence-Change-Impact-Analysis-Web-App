import os
import json
import shutil
from pathlib import Path
from typing import List, Dict
from services.ingestion import get_project_path
from services.parser import parse_file

BASE_DIR = Path(__file__).resolve().parent.parent
METADATA_BASE_PATH = BASE_DIR / "metadata"

def get_metadata_path(project_id: str) -> Path:
    return METADATA_BASE_PATH / project_id

def parse_project(project_id: str) -> Dict:
    project_path = get_project_path(project_id)
    metadata_path = get_metadata_path(project_id)
    
    # Clean previous metadata
    if metadata_path.exists():
        shutil.rmtree(metadata_path)
    os.makedirs(metadata_path, exist_ok=True)
    
    parsed_count = 0
    errors = []
    
    # Walk through the project
    for root, _, files in os.walk(project_path):
        for file in files:
            if file.endswith(".py"):
                full_path = Path(root) / file
                relative_path = full_path.relative_to(project_path)
                
                # Parse
                result = parse_file(str(full_path))
                
                # Inject relative path for frontend usage
                result["relative_path"] = str(relative_path)
                
                # Save metadata
                # Structure: metadata/project_id/path/to/file.py.json
                # We flatten directory structure or replicate it? 
                # Replicating is safer for collisions.
                target_meta_file = metadata_path / relative_path.with_suffix(".py.json")
                
                # Ensure parent dirs exist
                os.makedirs(target_meta_file.parent, exist_ok=True)
                
                with open(target_meta_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2)
                
                if "error" in result:
                    errors.append(result)
                else:
                    parsed_count += 1

    return {
        "status": "completed",
        "parsed_files": parsed_count,
        "errors": len(errors),
        "metadata_path": str(metadata_path)
    }

def get_file_metadata(project_id: str, path: str) -> Dict:
    metadata_path = get_metadata_path(project_id)
    project_root = get_project_path(project_id).resolve()
    
    # Handle absolute paths from frontend
    path_obj = Path(path)
    if path_obj.is_absolute():
        try:
            # Try to make it relative to the real project root
            # We must be careful about resolving symlinks or case sensitivity on Windows
            path_obj = path_obj.resolve().relative_to(project_root)
        except ValueError:
            # Fallback: maybe the frontend sent a path that doesn't match our resolved root?
            # Try string manipulation if simple resolution fails (weird windows drive letter casing)
            pass

    target_file = metadata_path / path_obj.with_suffix(".py.json")
    
    if not target_file.exists():
        return None
        
    with open(target_file, "r", encoding="utf-8") as f:
        return json.load(f)
