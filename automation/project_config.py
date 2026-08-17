import os
import yaml
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class OptionalServiceConfig(BaseModel):
    enabled: bool = False
    config: Dict[str, Any] = Field(default_factory=dict)

class ProjectConfig(BaseModel):
    project_id: str
    project_name: str
    project_root: str
    repository: str
    default_branch: str
    development_branch: str
    
    governance_docs: List[str] = Field(default_factory=list)
    roadmap_path: str = ""
    current_status_path: str = ""
    todo_path: str = ""
    
    supabase: OptionalServiceConfig = Field(default_factory=OptionalServiceConfig)
    vercel: OptionalServiceConfig = Field(default_factory=OptionalServiceConfig)
    browser_qa: OptionalServiceConfig = Field(default_factory=OptionalServiceConfig)
    
    test_commands: List[str] = Field(default_factory=list)
    build_commands: List[str] = Field(default_factory=list)
    
    def resolve_root(self, registry_dir: str) -> str:
        """Resolve the project_root into an absolute path."""
        repo_root = Path(registry_dir).parent
        
        path = Path(self.project_root)
        if path.is_absolute():
            resolved = path
        else:
            resolved = (repo_root / path).resolve()
            
        if not resolved.exists() or not resolved.is_dir():
            raise ValueError(f"Project root {resolved} does not exist or is not a directory.")
            
        return str(resolved)
