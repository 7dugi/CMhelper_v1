import os
import hashlib
from typing import List, Dict
from .config import PROJECT_ROOT
from .models import LoadedDocument

CORE_DOCUMENTS = [
    ".agents/AGENTS.md",
    "docs/PROJECT_OVERVIEW.md",
    "docs/CURRENT_STATUS.md",
    "docs/DEVELOPMENT_GATE.md",
    "docs/TECHNICAL_PRINCIPLES.md",
    "docs/ROADMAP.md",
    "docs/TODO.md",
    "docs/UI_INFORMATION_ARCHITECTURE.md"
]

class GovernanceLoader:
    def get_core_documents(self) -> List[str]:
        return CORE_DOCUMENTS

    def _is_safe_path(self, path: str) -> bool:
        abs_target = os.path.abspath(os.path.join(PROJECT_ROOT, path))
        return abs_target.startswith(PROJECT_ROOT)

    def load_document(self, path: str) -> LoadedDocument:
        if not self._is_safe_path(path):
            return LoadedDocument(path=path, exists=False, loaded=False)
            
        full_path = os.path.join(PROJECT_ROOT, path)
        if not os.path.exists(full_path):
            return LoadedDocument(path=path, exists=False, loaded=False)
            
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
                sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
                return LoadedDocument(path=path, exists=True, loaded=True, content=content, sha256=sha)
        except Exception:
            return LoadedDocument(path=path, exists=True, loaded=False)

    def load_core_documents(self) -> Dict[str, LoadedDocument]:
        return self.load_task_documents(self.get_core_documents())

    def load_task_documents(self, paths: List[str]) -> Dict[str, LoadedDocument]:
        result = {}
        for path in paths:
            result[path] = self.load_document(path)
        return result

    def validate_documents(self, loaded_docs: Dict[str, LoadedDocument]) -> bool:
        return all(doc.loaded for doc in loaded_docs.values())
