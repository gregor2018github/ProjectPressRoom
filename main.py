"""
Development entry point for Pressroom.
Run from the project root: python main.py [options]

If the backend venv is not activated, this script re-launches itself using
the venv Python automatically — no manual activation required.
"""
import argparse
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent
BACKEND_SRC = ROOT / "backend" / "src"

# Cross-platform venv Python path
_venv = ROOT / "backend" / ".venv"
VENV_PYTHON = _venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def _ensure_venv() -> None:
    """Re-launch with the venv Python if we're not already inside it."""
    if not VENV_PYTHON.exists():
        print(
            "ERROR: backend venv not found.\n"
            "Run:  cd backend\n"
            "      python -m venv .venv\n"
            "      .venv\\Scripts\\pip install -e .[dev]   # Windows\n"
            "      .venv/bin/pip install -e .[dev]        # Linux/macOS",
            file=sys.stderr,
        )
        sys.exit(1)
    if Path(sys.executable).resolve() != VENV_PYTHON.resolve():
        sys.exit(subprocess.run([str(VENV_PYTHON), __file__] + sys.argv[1:]).returncode)


def _build_frontend() -> None:
    frontend = ROOT / "frontend"
    if not (frontend / "package.json").exists():
        print("ERROR: frontend/package.json not found — skipping build.", file=sys.stderr)
        return
    print("Building frontend...")
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=frontend,
        shell=(sys.platform == "win32"),
    )
    if result.returncode != 0:
        print("Frontend build failed.", file=sys.stderr)
        sys.exit(1)
    print("Frontend build complete.")


def _open_browser(url: str, delay: float = 2.0) -> None:
    def _open() -> None:
        time.sleep(delay)
        webbrowser.open(url)

    threading.Thread(target=_open, daemon=True).start()


def _init_db() -> None:
    """Run pending migrations so a fresh checkout works on first start."""
    from pressroom.config import settings
    from pressroom.db.connection import run_migrations

    applied = run_migrations(settings.db_path)
    if applied:
        print(f"DB initialised ({applied} migration(s) applied).")


def main() -> None:
    _ensure_venv()

    sys.path.insert(0, str(BACKEND_SRC))

    parser = argparse.ArgumentParser(
        description="Start Pressroom (development)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--skip-build", action="store_true", help="Skip the frontend npm build")
    parser.add_argument("--no-browser", action="store_true", help="Don't open the browser")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    args = parser.parse_args()

    # Enable CORS for the Vite dev server by default when using this entry point.
    os.environ.setdefault("PRESSROOM_DEV", "1")

    if not args.skip_build:
        _build_frontend()

    # Match start.ps1: run with backend/ as CWD so all relative paths
    # (db_path, sources.toml, …) resolve to the same locations as before.
    os.chdir(ROOT / "backend")

    _init_db()

    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        _open_browser(url)

    import uvicorn
    from pressroom.api.app import create_app

    print(f"\nStarting Pressroom at {url}")
    print("Press Ctrl-C to stop.\n")
    uvicorn.run(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
