import os
import shutil
import uuid
import git
from pathlib import Path

BASE_STORAGE_PATH = Path("backend/storage")

def clone_repository(repo_url: str) -> str:
    """
    Clones a git repository into a unique temporary directory.
    Returns the project_id (folder name).
    """
    project_id = str(uuid.uuid4())
    target_dir = BASE_STORAGE_PATH / project_id
    
    # Ensure storage exists
    os.makedirs(BASE_STORAGE_PATH, exist_ok=True)
    
    try:
        print(f"Cloning {repo_url} into {target_dir}...")
        git.Repo.clone_from(repo_url, target_dir, depth=1)
        return project_id
    except Exception as e:
        # Cleanup if failed
        if target_dir.exists():
            shutil.rmtree(target_dir)
        raise Exception(f"Failed to clone repository: {str(e)}")

def get_project_path(project_id: str) -> Path:
    return BASE_STORAGE_PATH / project_id
