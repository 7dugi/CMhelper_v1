import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional
from .project_config import ProjectConfig

class ProjectRegistry:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.projects_dir = self.root_dir / "projects"
        self.projects: Dict[str, ProjectConfig] = {}
        self.load_all()
        
    def load_all(self):
        if not self.projects_dir.exists():
            return
            
        for yaml_file in self.projects_dir.glob("*.yaml"):
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data:
                        config = ProjectConfig(**data)
                        # Validate root resolution
                        config.resolve_root(str(self.projects_dir))
                        self.projects[config.project_id] = config
            except Exception as e:
                print(f"Failed to load project config from {yaml_file}: {e}")

    def get_project(self, project_id: str) -> Optional[ProjectConfig]:
        return self.projects.get(project_id)

    def list_projects(self) -> List[ProjectConfig]:
        return list(self.projects.values())

    def get_default_project(self) -> Optional[ProjectConfig]:
        # Fallback for backward compatibility
        if "cmhelper" in self.projects:
            return self.projects["cmhelper"]
        if self.projects:
            return next(iter(self.projects.values()))
        return None
