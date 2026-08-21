# Vercel Preview Deployment & Dependency Architecture

## 1. Overview & Architectural Context

CMhelper uses Vercel for hosting its web application frontend and serverless Python backend functions (`api/index.py` routing into FastAPI `CMhelper_web/backend/app.main`).

When Vercel builds Python Serverless Functions, it automatically inspects the repository root `requirements.txt` to install the runtime dependencies into the serverless function bundle. Previously, root `requirements.txt` contained both FastAPI web runtime packages and Harness automation dependencies (`discord.py`, `PyYAML`, `psutil`, `playwright`). 

Packaging heavy automation dependencies into serverless function bundles causes several issues:
- Unnecessary function bundle bloat, risking Vercel's 50MB zipped serverless function size limit.
- Slower build and cold-start execution times due to unused C-extensions and large libraries (such as Playwright and Discord bot dependencies).
- Increased attack surface and potential incompatibility with AWS Lambda / Vercel Python runtime environments.

To address this, dependency manifests are separated into a **Runtime Manifest** (`requirements.txt`) and a **Harness Manifest** (`requirements-harness.txt`).

---

## 2. Manifest Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              requirements-harness.txt                       │
│  (Windows Supervisor, Discord Bot, Process Monitor, QA)     │
│  - discord.py>=2.4.0                                        │
│  - PyYAML                                                   │
│  - psutil                                                   │
│  - playwright                                               │
│  -r requirements.txt                                        │
└──────────────────────────┬──────────────────────────────────┘
                           │ includes (-r)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 requirements.txt                            │
│        (Vercel/uv Flat Python Runtime Manifest)             │
│  - fastapi, uvicorn[standard], sqlalchemy, pydantic         │
│  - openpyxl, python-multipart, psycopg2-binary, supabase    │
│  - requests, PyJWT>=2.8.0, bcrypt, python-dotenv            │
└──────────────────────────┬──────────────────────────────────┘
                           │ 1:1 declaration parity
                           ▼
┌─────────────────────────────────────────────────────────────┐
│          CMhelper_web/backend/requirements.txt              │
│          (FastAPI Backend Source of Truth)                  │
│  - fastapi, uvicorn[standard], sqlalchemy, pydantic         │
│  - openpyxl, python-multipart, psycopg2-binary, supabase    │
│  - requests, PyJWT>=2.8.0, bcrypt, python-dotenv            │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 Root Runtime Manifest (`requirements.txt`)
- **Target:** Vercel Python Serverless Functions (`api/index.py`).
- **Implementation:** Flat manifest containing every runtime dependency verbatim from `CMhelper_web/backend/requirements.txt` (parsed cleanly by Vercel/uv without `-r` include directives).
- **Scope:** Contains only backend runtime dependencies required by FastAPI (`app.main`). Excludes all Harness-only packages (`playwright`, `discord.py`, `psutil`, `PyYAML`).

### 2.2 Dedicated Harness Manifest (`requirements-harness.txt`)
- **Target:** Local Windows Supervisor, Discord notifications, process monitoring, and browser QA test suites.
- **Implementation:** Uses `-r requirements.txt` to inherit all backend runtime dependencies from the flat root manifest, plus the 4 relocated Harness packages:
  - `discord.py>=2.4.0` (Discord bot and notification adapters)
  - `PyYAML` (Operating layer and project config parsing)
  - `psutil` (Process management and Supervisor health checks)
  - `playwright` (Browser QA automation)

### 2.3 Backend Canonical Manifest (`CMhelper_web/backend/requirements.txt`)
- Canonical reference and source of truth matching all reachable imports from `api/index.py` -> `CMhelper_web/backend/app/main.py`. The root `requirements.txt` maintains exact 1:1 declaration parity with this file.

---

## 3. Local Windows Harness Installation Guide

For local development, Windows Supervisor execution, Discord bot operations, or browser QA, install dependencies using `requirements-harness.txt`:

```powershell
# Install both runtime and harness dependencies
pip install -r requirements-harness.txt

# (Optional) Install Playwright browser binaries if running browser QA locally
playwright install chromium
```

To verify the installation:
```powershell
# Verify Harness dependency resolution
python -m unittest automation/tests/test_vercel_dependency_separation.py
```

---

## 4. Vercel Root-Manifest Behavior & Routing Compatibility

- **Serverless Function Discovery:** Vercel discovers `api/index.py` and bundles it with dependencies defined in root `requirements.txt` (parsed directly as a flat runtime manifest by Vercel/uv).
- **Routing Integrity (`vercel.json`):**
  - `/api/(.*)` rewrites directly to `/api/index`.
  - Frontend fallback `/((?!api/.*).*)` rewrites to `/index.html`.
  - No frontend-only Root Directory configuration is set, ensuring the Python backend function remains fully discoverable and functional.

---

## 5. Preview-Only Rollout Policy & Guardrails

- **Preview Environment First:** All dependency updates and build verification must be performed on Vercel **Preview** deployments.
- **Production Gate:** Production deployments require explicit approval and must not be triggered automatically during routine Harness runs.
- **Build Verification:** Verify that:
  1. The Vercel function build succeeds without bundle size warnings.
  2. The generated Preview URL is accessible.
  3. API endpoints (e.g. `/api/health` or API route index) respond properly.

---

## 6. Non-Mutating Browser-QA Boundary

- **Read-Only Verification:** Browser QA running against Vercel Preview environments must strictly operate in **non-mutating (read-only)** mode.
- **Prohibited Actions:**
  - Creating test users or tenant records in shared / staging / production databases.
  - Submitting forms that trigger database mutations or external third-party API calls (e.g., KakaoTalk sending, Supabase table mutations).
- **Boundary Duration:** Mutating browser QA is deferred until dedicated isolated test tenants and ephemeral staging databases are formally provisioned and approved.

---

## 7. Rollback Procedure

If a dependency issue or regression occurs during Vercel deployment:

1. **Revert Manifest Changes:**
   - Revert `requirements.txt` to its previous direct declarations or previous commit.
   - Delete `requirements-harness.txt` if needed.
2. **Deploy to Preview:**
   - Trigger a Preview deployment on Vercel to validate build success and function execution.
3. **Verify Preview Health:**
   - Check the Preview build logs and verify that serverless functions initialize without missing module errors.
4. **Isolate Scope:**
   - Do not touch `vercel.json`, backend business logic, or database migrations during dependency rollback. Revert only the manifest change and validate Preview status before taking any broader action.
