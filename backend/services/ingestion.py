import os
import shutil
import uuid
import git
import stat
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BASE_STORAGE_PATH = BASE_DIR / "storage"

def remove_readonly(func, path, excinfo):
    """Helper to remove read-only attribute and retry deletion (Windows fix)."""
    os.chmod(path, stat.S_IWRITE)
    func(path)

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
        print(f"DEBUG: Starting clone for {repo_url}", flush=True)
        # Verify git is available
        print(f"DEBUG: Git version check", flush=True)
        
        # Configure env to prevent prompts (GIT_TERMINAL_PROMPT=0)
        env = os.environ.copy()
        env['GIT_TERMINAL_PROMPT'] = '0'
        
        print(f"Cloning {repo_url} into {target_dir}...", flush=True)
        # Enable longpaths for Windows
        git.Repo.clone_from(
            repo_url, 
            target_dir, 
            depth=1, 
            env=env, 
            multi_options=['-c core.longpaths=true'],
            allow_unsafe_options=True
        )
        print("DEBUG: Clone complete", flush=True)
        return project_id
    except Exception as e:
        # Cleanup if failed
        if target_dir.exists():
            try:
                shutil.rmtree(target_dir, onerror=remove_readonly)
            except Exception as cleanup_error:
                print(f"DEBUG: Failed to cleanup {target_dir}: {cleanup_error}", flush=True)
                
        # Re-raise the original error so we know why it failed
        raise Exception(f"Failed to clone repository: {str(e)}")

def get_project_path(project_id: str) -> Path:
    return BASE_STORAGE_PATH / project_id
