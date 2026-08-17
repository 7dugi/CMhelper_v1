import os
from pathlib import Path

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

SENIOR_PROVIDER = "codex"
IMPLEMENTER_PROVIDER = "antigravity"
DESIGNER_PROVIDER = "disabled"

MAX_AUTONOMOUS_REVIEW_ITERATIONS = 3
NO_PROGRESS_THRESHOLD = 2
OSCILLATION_THRESHOLD = 2

DISCORD_ENABLED = False
VERCEL_ENABLED = False
BROWSER_QA_ENABLED = False

DRY_RUN = True
