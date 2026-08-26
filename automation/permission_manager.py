import json
import os
import shutil
from pathlib import Path
from typing import List, Optional

class PermissionManager:
    """
    Manages Antigravity CLI's scoped write permissions dynamically.
    Backs up settings.json and injects specific write_file permissions for the duration of the task.
    """
    
    def __init__(self):
        # The official settings path for the CLI
        self.settings_path = Path.home() / ".gemini" / "antigravity-cli" / "settings.json"
        self.backup_path = self.settings_path.with_suffix(".json.bak")

    def _ensure_paths(self):
        if not self.settings_path.exists():
            raise FileNotFoundError(f"Antigravity CLI settings not found at {self.settings_path}")

    def apply_scoped_permissions(self, allowed_paths: List[str]) -> bool:
        """
        Creates a backup of settings.json and adds temporary write_file rules for allowed_paths.
        Returns True if successful.
        """
        self._ensure_paths()
        
        # 1. Backup
        try:
            shutil.copy2(self.settings_path, self.backup_path)
        except Exception as e:
            print(f"PermissionManager: Failed to backup settings.json: {e}")
            return False

        # 2. Read existing
        try:
            with open(self.settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        except Exception as e:
            print(f"PermissionManager: Failed to read settings.json: {e}")
            self.restore_permissions()
            return False

        # 3. Inject new permissions
        if 'permissions' not in settings:
            settings['permissions'] = {}
        if 'allow' not in settings['permissions']:
            settings['permissions']['allow'] = []

        allow_list = settings['permissions']['allow']
        
        for p in allowed_paths:
            rule = f"write_file({p})"
            if "*" in p or p.endswith("/"):
                print(f"PermissionManager: Invalid allowed path {p}. Wildcards or directories are not allowed.")
                self.restore_permissions()
                return False
            if rule not in allow_list:
                allow_list.append(rule)

        # 4. Write back
        try:
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)
            return True
        except Exception as e:
            print(f"PermissionManager: Failed to write settings.json: {e}")
            self.restore_permissions()
            return False

    def restore_permissions(self) -> bool:
        """
        Restores settings.json from the backup.
        Returns True if successful.
        """
        if not self.backup_path.exists():
            print("PermissionManager: No backup found to restore.")
            return False
            
        try:
            shutil.move(self.backup_path, self.settings_path)
            return True
        except Exception as e:
            print(f"PermissionManager: Failed to restore settings.json: {e}")
            return False
