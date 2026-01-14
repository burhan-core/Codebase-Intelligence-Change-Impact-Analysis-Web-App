from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from services.ingestion import clone_repository, get_project_path
from services.scanner import scan_directory
from services.analysis import parse_project, get_file_metadata

# ... imports ...

app = FastAPI(title="Codebase Intelligence API", version="1.0.0")

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class IngestRequest(BaseModel):
    url: str

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Backend is online"}

@app.post("/api/project/{project_id}/parse")
def trigger_parse(project_id: str):
    try:
        result = parse_project(project_id)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/project/{project_id}/metadata")
def get_metadata(project_id: str, path: str):
    """
    Returns parsed metadata for a specific file.
    Path should be relative to project root.
    """
    data = get_file_metadata(project_id, path)
    if data is None:
        return {"classes": [], "functions": [], "imports": []}
    return data

@app.post("/api/ingest")
def ingest_repository(request: IngestRequest):
    try:
        project_id = clone_repository(request.url)
        project_path = get_project_path(project_id)
        
        # Auto-scan file tree
        file_tree = scan_directory(project_path)
        
        # Auto-parse for Phase 2
        # (Optional: we can do this async or let frontend trigger it. 
        # Frontend currently triggers it in OverviewPage, so we can skip calling it here 
        # to keep request fast.)
        
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
    
    # Handle both absolute (from FileTree) and relative (from Graph) paths
    target_path = Path(path)
    if target_path.is_absolute():
        target_file = target_path.resolve()
    else:
        target_file = (project_root / target_path).resolve()

    # Security check: Ensure file is within project root
    if not str(target_file).startswith(str(project_root)):
        raise HTTPException(status_code=403, detail="Access denied: File outside project root")

    if not target_file.exists():
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        content = target_file.read_text(encoding='utf-8', errors='replace')
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")

# --- Phase 3: Dependency Graph API ---

from services.graph import build_graph

# Simple in-memory cache for graphs: project_id -> DependencyGraph
# In production, use Redis or similar.
GRAPH_CACHE = {}

@app.get("/api/project/{project_id}/dependencies")
def get_dependencies(project_id: str, node_id: str = None):
    """
    Returns dependency information for the graph or a specific node.
    If node_id is provided, returns callers/callees.
    If node_id is NOT provided, returns the full graph (for visualization).
    """
    # 1. Get or Build Graph
    if project_id not in GRAPH_CACHE:
        # Check if project exists first?
        # For now, just try to build it.
        try:
            GRAPH_CACHE[project_id] = build_graph(project_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to build graph: {str(e)}")
    
    dg = GRAPH_CACHE[project_id]
    
    # 2. Handle Node Query
    if node_id:
        node = dg.get_node(node_id)
        if not node:
            raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
            
        return {
            "node": node,
            "callers": dg.get_callers(node_id),
            "callees": dg.get_callees(node_id)
        }
    
    # 3. Return Full Graph
    return dg.toJson()

@app.post("/api/project/{project_id}/rebuild_graph")
def rebuild_graph_endpoint(project_id: str):
    """Force rebuild of the dependency graph."""
    try:
        GRAPH_CACHE[project_id] = build_graph(project_id)
        return {"status": "ok", "message": "Graph rebuilt successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

