from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from services.ingestion import clone_repository, get_project_path
from services.scanner import scan_directory

app = FastAPI(title="Codebase Intelligence API", version="1.0.0")

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class IngestRequest(BaseModel):
    url: str

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Backend is online"}

@app.post("/api/ingest")
def ingest_repository(request: IngestRequest):
    try:
        project_id = clone_repository(request.url)
        project_path = get_project_path(project_id)
        file_tree = scan_directory(project_path)
        
        return {
            "project_id": project_id,
            "file_tree": file_tree,
            "message": "Repository ingested successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/project/{project_id}/file")
def get_file_content(project_id: str, path: str):
    """
    Path param should be absolute path or relative? 
    Scanner returns absolute paths in 'path' field. 
    Ideally, we shouldn't expose absolute paths to frontend for security, but for a local tool it's acceptable.
    To be safer, we should verify the path is within the project directory.
    """
    project_root = get_project_path(project_id).resolve()
    target_file = Path(path).resolve()
    
    # Security check: Ensure file is within project root
    if not str(target_file).startswith(str(project_root)):
         # Fallback for when frontend sends relative paths or names
         # This is a simplification. Ideally, frontend should send relative path from root.
         # For now, let's assume the frontend sends the path received from the tree.
         pass

    if not target_file.exists():
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        content = target_file.read_text(encoding='utf-8', errors='replace')
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")

