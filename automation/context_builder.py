import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from .project_config import ProjectConfig
from .models import LoadedDocument, TaskContext

class ContextBuilder:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        
    def _load_doc(self, project_root: Path, relative_path: str) -> LoadedDocument:
        if not relative_path:
            return LoadedDocument(path="", exists=False, loaded=False)
            
        full_path = project_root / relative_path
        if not full_path.exists():
            return LoadedDocument(path=relative_path, exists=False, loaded=False)
            
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            import hashlib
            sha = hashlib.sha256(content.encode('utf-8')).hexdigest()
            return LoadedDocument(path=relative_path, exists=True, loaded=True, content=content, sha256=sha)
        except Exception as e:
            print(f"Error loading {relative_path}: {e}")
            return LoadedDocument(path=relative_path, exists=True, loaded=False)

    def build_context(self, config: ProjectConfig, registry_dir: str) -> Dict[str, Any]:
        """
        Loads the core documents and returns a structured Context Bundle.
        """
        proj_root = Path(config.resolve_root(registry_dir))
        
        bundle = {
            "project_id": config.project_id,
            "project_name": config.project_name,
            "development_branch": config.development_branch,
            "phase_info": "Unknown",
            "roadmap_relevant": "",
            "todo_candidates": "",
            "governance_constraints": [],
            "documents": {}
        }
        
        # Load Status
        status_doc = self._load_doc(proj_root, config.current_status_path)
        if status_doc.loaded:
            bundle["documents"]["status"] = status_doc.content
            # Extract basic phase info from status
            lines = status_doc.content.split('\n')
            for line in lines[:20]:
                if "Phase" in line or "Status" in line:
                    bundle["phase_info"] = bundle.get("phase_info", "") + line + "\n"
                    
        # Load Roadmap
        roadmap_doc = self._load_doc(proj_root, config.roadmap_path)
        if roadmap_doc.loaded:
            bundle["documents"]["roadmap"] = roadmap_doc.content
            bundle["roadmap_relevant"] = "Loaded (Refer to attached documents)"
            
        # Load TODO
        todo_doc = self._load_doc(proj_root, config.todo_path)
        if todo_doc.loaded:
            bundle["documents"]["todo"] = todo_doc.content
            bundle["todo_candidates"] = "Loaded (Refer to attached documents)"
            
        # Load Governance
        for doc_path in config.governance_docs:
            g_doc = self._load_doc(proj_root, doc_path)
            if g_doc.loaded:
                bundle["documents"][doc_path] = g_doc.content
                bundle["governance_constraints"].append(f"Loaded: {doc_path}")
                
        return bundle
