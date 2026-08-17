import json
import os
import psutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field

class TaskExecutionLockData(BaseModel):
    task_id: str
    pid: int
    started_at: datetime = Field(default_factory=datetime.utcnow)
    heartbeat_at: datetime = Field(default_factory=datetime.utcnow)

class TaskLockManager:
    def __init__(self, root_dir: str):
        self.lock_dir = Path(root_dir) / "automation" / "runtime"
        self.lock_file = self.lock_dir / "execution.lock"
        self.lock_dir.mkdir(parents=True, exist_ok=True)

    def _read_lock(self) -> Optional[TaskExecutionLockData]:
        if not self.lock_file.exists():
            return None
        try:
            with open(self.lock_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return TaskExecutionLockData(**data)
        except Exception:
            return None

    def _is_process_running(self, pid: int) -> bool:
        try:
            p = psutil.Process(pid)
            return p.is_running() and p.status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return False

    def is_locked(self) -> bool:
        lock_data = self._read_lock()
        if not lock_data:
            return False
        
        # Check if the process is actually running
        if self._is_process_running(lock_data.pid):
            return True
            
        # Stale lock
        return False

    def acquire(self, task_id: str) -> bool:
        if self.is_locked():
            lock_data = self._read_lock()
            if lock_data and lock_data.task_id == task_id and lock_data.pid == os.getpid():
                # Already own it
                return True
            return False

        data = TaskExecutionLockData(task_id=task_id, pid=os.getpid())
        
        temp_file = self.lock_file.with_suffix('.lock.tmp')
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(data.model_dump_json(indent=2))
                f.flush()
                os.fsync(f.fileno())
            # Atomic replace
            temp_file.replace(self.lock_file)
            return True
        except Exception:
            if temp_file.exists():
                temp_file.unlink()
            return False

    def heartbeat(self):
        lock_data = self._read_lock()
        if lock_data and lock_data.pid == os.getpid():
            lock_data.heartbeat_at = datetime.utcnow()
            temp_file = self.lock_file.with_suffix('.lock.tmp')
            try:
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(lock_data.model_dump_json(indent=2))
                    f.flush()
                    os.fsync(f.fileno())
                temp_file.replace(self.lock_file)
            except Exception:
                if temp_file.exists():
                    temp_file.unlink()

    def release(self, task_id: str):
        lock_data = self._read_lock()
        if lock_data and lock_data.task_id == task_id and lock_data.pid == os.getpid():
            if self.lock_file.exists():
                self.lock_file.unlink()
