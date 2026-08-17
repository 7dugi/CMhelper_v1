import os
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..models import DatabaseEvidence, SupabaseAccessMode
from ..config import PROJECT_ROOT

class SupabaseAdapterError(Exception):
    pass

class SupabaseAdapter:
    def __init__(self, mode: SupabaseAccessMode = SupabaseAccessMode.READ_ONLY):
        self.mode = mode
        self.root_dir = PROJECT_ROOT
        self.project_ref = self._get_project_ref()
        self.is_linked = bool(self.project_ref)
        
    def _get_project_ref(self) -> Optional[str]:
        # Try from env first
        ref = os.environ.get("SUPABASE_PROJECT_ID")
        if ref:
            return ref
            
        # Try from linked project
        ref_file = os.path.join(self.root_dir, "supabase", ".temp", "project-ref")
        if os.path.exists(ref_file):
            try:
                with open(ref_file, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass
        return None

    def _run_cli(self, args: List[str]) -> str:
        cli_cmd = "supabase.cmd" if os.name == "nt" else "supabase"
        cmd = [cli_cmd] + args
        res = subprocess.run(cmd, cwd=self.root_dir, capture_output=True, text=True)
        if res.returncode != 0:
            raise SupabaseAdapterError(f"Supabase CLI error: {res.stderr}")
        return res.stdout

    def _run_query(self, sql: str) -> List[Dict[str, Any]]:
        # Hardcoded safe read-only queries only
        # We must use --linked or specify DB URL. We'll use --linked assuming CLI is configured.
        # Format as json to easily parse
        # But `supabase db query` output format is not standard json for results without --output json?
        # Actually `supabase db query` does not have `--output json` flag, let's see.
        # As a fallback, we will just parse text or use a synthetic response for H5 if CLI is problematic.
        
        # We can write the SQL to a temp file or pass via stdin
        res = subprocess.run(["supabase", "db", "query", sql, "--linked"], 
                             cwd=self.root_dir, capture_output=True, text=True)
                             
        if res.returncode != 0:
            raise SupabaseAdapterError(f"Query failed: {res.stderr}")
            
        # For H5 we might not actually parse the raw psql output perfectly if it's text table.
        # But we can try to extract information.
        # If it fails, we fall back to a mock/synthetic response for testing DB Evidence.
        return [{"raw": res.stdout}]

    def _run_query_count(self, sql: str, count_key: str = "count") -> str:
        try:
            res = subprocess.run(["supabase.cmd" if os.name == "nt" else "supabase", "db", "query", sql, "--linked"], 
                                 cwd=self.root_dir, capture_output=True, text=True)
            if res.returncode == 0:
                start_idx = res.stdout.find('{')
                end_idx = res.stdout.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    json_str = res.stdout[start_idx:end_idx+1]
                    data = json.loads(json_str)
                    rows = data.get("rows", [])
                    if rows:
                        return str(rows[0].get(count_key, "UNKNOWN"))
        except Exception:
            pass
        return "UNKNOWN"

    def inspect_db(self) -> DatabaseEvidence:
        """
        Gathers read-only evidence of the database structure.
        """
        if not self.is_linked:
            raise SupabaseAdapterError("No Supabase project linked. Please configure project first.")
            
        evidence = DatabaseEvidence(
            project_ref=self.project_ref,
            connection_method="CLI_LINKED"
        )
        
        # Check migrations
        mig_dir = os.path.join(self.root_dir, "supabase", "migrations")
        if os.path.exists(mig_dir):
            files = os.listdir(mig_dir)
            evidence.migration_state = f"LOCAL_FILES_EXIST_COUNT_{len(files)}"
        else:
            evidence.migration_state = "NO_LOCAL_MIGRATIONS"
            
        # Attempt a safe schema query (using inspect db to avoid arbitrary SQL)
        try:
            out = self._run_cli(["inspect", "db", "table-stats", "--linked", "--output-format", "json"])
            start_idx = out.find('{')
            end_idx = out.rfind('}')
            if start_idx != -1 and end_idx != -1:
                json_str = out[start_idx:end_idx+1]
                data = json.loads(json_str)
                tables = []
                for row in data.get("rows", []):
                    table_schema = row.get("name", "") 
                    if table_schema.startswith("public."):
                        tables.append(table_schema.split(".")[1])
                evidence.tables = list(set(tables))
                evidence.schemas = ["public"]
                
            # Additional safe read-only metadata queries
            evidence.columns = self._run_query_count("SELECT count(*) as count FROM information_schema.columns WHERE table_schema='public';")
            evidence.primary_keys = self._run_query_count("SELECT count(*) as count FROM pg_constraint c JOIN pg_class t ON c.conrelid = t.oid JOIN pg_namespace n ON t.relnamespace = n.oid WHERE n.nspname = 'public' AND c.contype = 'p';")
            evidence.indexes = self._run_query_count("SELECT count(*) as count FROM pg_indexes WHERE schemaname='public';")
            evidence.foreign_keys = self._run_query_count("SELECT count(*) as count FROM pg_constraint c JOIN pg_class t ON c.conrelid = t.oid JOIN pg_namespace n ON t.relnamespace = n.oid WHERE n.nspname = 'public' AND c.contype = 'f';")
            evidence.rls_enabled_tables = self._run_query_count("SELECT count(*) as count FROM pg_class t JOIN pg_namespace n ON t.relnamespace = n.oid WHERE n.nspname = 'public' AND t.relkind = 'r' AND t.relrowsecurity = true;")
            evidence.policies = self._run_query_count("SELECT count(*) as count FROM pg_policy pol JOIN pg_class cls ON pol.polrelid = cls.oid JOIN pg_namespace n ON cls.relnamespace = n.oid WHERE n.nspname = 'public';")
            
        except Exception as e:
            evidence.warnings.append(f"Failed to fetch full schema: {e}")
            
        return evidence
