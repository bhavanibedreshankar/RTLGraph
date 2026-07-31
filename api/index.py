"""Vercel serverless entrypoint.

Vercel auto-detects any .py file under /api as a Python function. This one
loads the real FastAPI app (src/api/main.py) and mounts it under the /api
prefix so the deployed surface matches what the frontend already calls in
dev (ui/src/api.ts's BASE = '/api', proxied to the app's own root paths).

Uses importlib with an explicit file path rather than `from api.main import
app`: this repo-root /api directory is itself a package named "api" (Vercel's
convention), which collides with src/api -- a dotted import resolves against
whichever "api" package Python already cached in sys.modules first, not
necessarily the one on our prepended sys.path.
"""

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

_spec = importlib.util.spec_from_file_location("rtlgraph_api_main", SRC_DIR / "api" / "main.py")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
rtlgraph_app = _module.app

# Build the graph/engine synchronously here, at import time (i.e. once per
# cold start), rather than relying on rtlgraph_app's `lifespan` hook. Starlette
# does not guarantee a mounted sub-app's lifespan runs before it serves its
# first request, so leaving this to `lifespan` let concurrent requests on a
# fresh instance race into `get_engine()` and corrupt the shared /tmp SQLite
# cache (surfaced as intermittent 500s -- see get_engine's lock for the other
# half of this fix).
_module.get_engine()

from fastapi import FastAPI  # noqa: E402

app = FastAPI()
app.mount("/api", rtlgraph_app)
