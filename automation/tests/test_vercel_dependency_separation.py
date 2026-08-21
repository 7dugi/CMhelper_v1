import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from typing import List, Set, Tuple


def normalize_package_name(requirement_line: str) -> str:
    """
    Extracts the normalized canonical package name from a pip requirement string.
    Example: 'uvicorn[standard]>=0.20.0' -> 'uvicorn', 'discord.py>=2.4.0' -> 'discord.py'
    """
    cleaned = requirement_line.strip()
    if not cleaned or cleaned.startswith("#") or cleaned.startswith("-"):
        return ""
    # Strip inline comments
    if " #" in cleaned:
        cleaned = cleaned.split(" #", 1)[0].strip()
    # Strip environment markers (e.g. ; python_version >= '3.8')
    if ";" in cleaned:
        cleaned = cleaned.split(";", 1)[0].strip()
    # Match package name part before extras and version specifiers
    match = re.match(r"^([A-Za-z0-9_.\-]+)", cleaned)
    if match:
        return match.group(1).lower()
    return ""


def resolve_requirements(file_path: Path, visited: Set[Path] = None) -> List[Tuple[str, Path]]:
    """
    Recursively resolves a pip requirements file following -r / --requirement includes.
    Returns a list of tuples: (raw_requirement_line, source_file_path).
    """
    if visited is None:
        visited = set()

    resolved_path = file_path.resolve()
    if resolved_path in visited:
        return []
    visited.add(resolved_path)

    if not resolved_path.exists():
        raise FileNotFoundError(f"Requirements file not found: {resolved_path}")

    results: List[Tuple[str, Path]] = []
    with open(resolved_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if " #" in line:
                line = line.split(" #", 1)[0].strip()

            if line.startswith("-r ") or line.startswith("--requirement "):
                target_str = line.split(maxsplit=1)[1].strip()
                # Resolve relative to the directory of the current requirements file
                target_path = (resolved_path.parent / target_str).resolve()
                if not target_path.exists():
                    # Fallback relative to repository root if not found relative to parent
                    repo_root = Path(__file__).resolve().parent.parent.parent
                    fallback_path = (repo_root / target_str).resolve()
                    if fallback_path.exists():
                        target_path = fallback_path
                results.extend(resolve_requirements(target_path, visited))
            else:
                results.append((line, resolved_path))

    return results


class TestVercelDependencySeparation(unittest.TestCase):
    """
    Harness regression test suite validating the separation of Vercel Python runtime
    manifest and local Harness-only dependencies.
    """

    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parent.parent.parent
        cls.root_req_path = cls.repo_root / "requirements.txt"
        cls.harness_req_path = cls.repo_root / "requirements-harness.txt"
        cls.backend_req_path = cls.repo_root / "CMhelper_web" / "backend" / "requirements.txt"
        cls.vercel_json_path = cls.repo_root / "vercel.json"

        cls.harness_only_packages = {"discord.py", "pyyaml", "psutil", "playwright"}

    def test_root_requirements_flat_manifest(self):
        """
        Acceptance Criterion [flat-root-runtime-manifest]:
        Root `requirements.txt` must be a flat manifest with no include directives (-r/--requirement),
        containing every declaration from CMhelper_web/backend/requirements.txt exactly once,
        and excluding all Harness-only declarations.
        """
        self.assertTrue(self.root_req_path.exists(), "Root requirements.txt must exist.")
        content = self.root_req_path.read_text(encoding="utf-8")
        lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]

        # Must not contain include directives (-r / --requirement)
        has_include_directive = any(
            re.match(r"^-(r|-requirement)\b", line)
            for line in lines
        )
        self.assertFalse(
            has_include_directive,
            f"Root requirements.txt must not contain include directives (-r/--requirement). Found: {lines}",
        )

        # Must contain exact declarations from backend manifest
        self.assertTrue(self.backend_req_path.exists(), "Backend requirements.txt must exist.")
        backend_content = self.backend_req_path.read_text(encoding="utf-8")
        backend_lines = [line.strip() for line in backend_content.splitlines() if line.strip() and not line.strip().startswith("#")]

        self.assertEqual(
            lines,
            backend_lines,
            f"Root requirements.txt must have exact parity with backend manifest declarations: {lines} != {backend_lines}",
        )

        # Must not declare any Harness-only packages
        direct_packages = {normalize_package_name(line) for line in lines}
        leaked_packages = direct_packages.intersection(self.harness_only_packages)
        self.assertEqual(
            leaked_packages,
            set(),
            f"Root requirements.txt directly declares Harness-only packages: {leaked_packages}",
        )

    def test_harness_requirements_manifest_structure(self):
        """
        Acceptance Criterion [harness-manifest]:
        A dedicated local Harness manifest retains the four relocated declarations
        unchanged and includes the root runtime manifest.
        """
        if not self.harness_req_path.exists():
            self.skipTest("requirements-harness.txt not present in workspace.")

        content = self.harness_req_path.read_text(encoding="utf-8")
        lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]

        # Must include root requirements.txt
        has_root_include = any(
            re.match(r"^-(r|-requirement)\s+.*requirements\.txt", line)
            for line in lines
        )
        self.assertTrue(
            has_root_include,
            f"requirements-harness.txt must include root requirements.txt. Found: {lines}",
        )

        # Must contain all 4 Harness-only packages
        declared_packages = {normalize_package_name(line) for line in lines if not line.startswith("-")}
        for pkg in self.harness_only_packages:
            self.assertIn(
                pkg,
                declared_packages,
                f"Harness manifest missing required harness dependency: {pkg}",
            )

    def test_backend_runtime_manifest_integrity(self):
        """
        Confirms CMhelper_web/backend/requirements.txt contains all FastAPI runtime dependencies
        and no harness-only dependencies.
        """
        self.assertTrue(self.backend_req_path.exists(), "Backend requirements.txt must exist.")
        content = self.backend_req_path.read_text(encoding="utf-8")
        lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]
        backend_packages = {normalize_package_name(line) for line in lines if not line.startswith("-")}

        expected_backend_deps = {
            "fastapi",
            "uvicorn",
            "sqlalchemy",
            "pydantic",
            "openpyxl",
            "python-multipart",
            "psycopg2-binary",
            "supabase",
            "requests",
            "pyjwt",
            "bcrypt",
            "python-dotenv",
        }
        self.assertTrue(
            expected_backend_deps.issubset(backend_packages),
            f"Backend requirements.txt missing expected runtime dependencies: {expected_backend_deps - backend_packages}",
        )

        # Ensure no harness packages in backend manifest
        self.assertEqual(
            backend_packages.intersection(self.harness_only_packages),
            set(),
            "Backend requirements.txt should not contain harness-only packages.",
        )

    def test_root_runtime_manifest_resolution(self):
        """
        Acceptance Criterion [runtime-import-coverage]:
        Recursively resolved root requirements.txt contains all backend runtime
        declarations and excludes all Harness-only packages.
        """
        resolved_root = resolve_requirements(self.root_req_path)
        resolved_root_packages = {normalize_package_name(line) for line, _ in resolved_root}

        resolved_backend = resolve_requirements(self.backend_req_path)
        backend_packages = {normalize_package_name(line) for line, _ in resolved_backend}

        # All backend packages must be present in root resolution
        missing_in_root = backend_packages - resolved_root_packages
        self.assertEqual(
            missing_in_root,
            set(),
            f"Root requirements.txt failed to resolve backend packages: {missing_in_root}",
        )

        # None of the harness-only packages should be present
        resolved_harness_leak = resolved_root_packages.intersection(self.harness_only_packages)
        self.assertEqual(
            resolved_harness_leak,
            set(),
            f"Harness packages leaked into resolved root runtime manifest: {resolved_harness_leak}",
        )

    def test_harness_manifest_resolution(self):
        """
        Acceptance Criterion [harness-manifest]:
        Recursively resolved requirements-harness.txt contains BOTH backend runtime
        packages and all 4 Harness-only packages.
        """
        if not self.harness_req_path.exists():
            self.skipTest("requirements-harness.txt not present in workspace.")

        resolved_harness = resolve_requirements(self.harness_req_path)
        resolved_harness_packages = {normalize_package_name(line) for line, _ in resolved_harness}

        resolved_backend = resolve_requirements(self.backend_req_path)
        backend_packages = {normalize_package_name(line) for line, _ in resolved_backend}

        # All backend packages must be present
        self.assertTrue(
            backend_packages.issubset(resolved_harness_packages),
            f"Harness manifest failed to resolve runtime dependencies: {backend_packages - resolved_harness_packages}",
        )

        # All harness-only packages must be present
        self.assertTrue(
            self.harness_only_packages.issubset(resolved_harness_packages),
            f"Harness manifest failed to resolve harness dependencies: {self.harness_only_packages - resolved_harness_packages}",
        )

    def test_vercel_routing_compatibility(self):
        """
        Acceptance Criterion [routing-compatibility]:
        vercel.json retains /api/(.*) -> /api/index rewrite and frontend fallback.
        """
        self.assertTrue(self.vercel_json_path.exists(), "vercel.json must exist.")
        data = json.loads(self.vercel_json_path.read_text(encoding="utf-8"))

        self.assertIn("rewrites", data)
        rewrites = data["rewrites"]

        api_rewrite = next((r for r in rewrites if r.get("source") == "/api/(.*)"), None)
        self.assertIsNotNone(api_rewrite, "Missing /api/(.*) rewrite in vercel.json")
        self.assertEqual(api_rewrite.get("destination"), "/api/index")

        frontend_rewrite = next((r for r in rewrites if "index.html" in r.get("destination", "")), None)
        self.assertIsNotNone(frontend_rewrite, "Missing frontend fallback rewrite to /index.html")

    def test_recursive_resolver_helper(self):
        """
        Validates that resolve_requirements handles nesting, comments, whitespace, and prevents cycles.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            base_file = tmp_path / "base.txt"
            mid_file = tmp_path / "mid.txt"
            top_file = tmp_path / "top.txt"

            base_file.write_text("package-a>=1.0\n# comment\npackage-b\n", encoding="utf-8")
            mid_file.write_text(f"-r base.txt\npackage-c\n", encoding="utf-8")
            top_file.write_text(f"-r mid.txt\n-r base.txt\npackage-d\n", encoding="utf-8")

            resolved = resolve_requirements(top_file)
            packages = [normalize_package_name(line) for line, _ in resolved]

            self.assertIn("package-a", packages)
            self.assertIn("package-b", packages)
            self.assertIn("package-c", packages)
            self.assertIn("package-d", packages)


if __name__ == "__main__":
    unittest.main()
