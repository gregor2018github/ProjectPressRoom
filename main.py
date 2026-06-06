"""
Development entry point for Pressroom.
Run from the project root: python main.py [options]

If the backend venv is not activated, this script re-launches itself using
the venv Python automatically — no manual activation required.
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
BACKEND_SRC = ROOT / "backend" / "src"
BROWSER_PROFILE = ROOT / "backend" / "data" / "browser_profile"

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


def _find_chromium_exe() -> Path | None:
    """Return a path to Edge or Chrome, or None if neither is found."""
    if sys.platform == "win32":
        candidates = [
            Path(os.environ.get("PROGRAMFILES(X86)", ""), "Microsoft/Edge/Application/msedge.exe"),
            Path(os.environ.get("PROGRAMFILES", ""),       "Microsoft/Edge/Application/msedge.exe"),
            Path(os.environ.get("PROGRAMFILES", ""),       "Google/Chrome/Application/chrome.exe"),
            Path(os.environ.get("PROGRAMFILES(X86)", ""), "Google/Chrome/Application/chrome.exe"),
            Path(os.environ.get("LOCALAPPDATA", ""),       "Google/Chrome/Application/chrome.exe"),
        ]
        return next((p for p in candidates if p.exists()), None)
    else:
        for cmd in ("google-chrome", "chromium-browser", "chromium", "microsoft-edge"):
            found = shutil.which(cmd)
            if found:
                return Path(found)
        return None


def _launch_browser(url: str) -> "subprocess.Popen[bytes] | None":
    """
    Open the app in a dedicated browser process that main.py can terminate.

    Uses a temporary profile directory so the instance is fully isolated from
    the user's main browser.  Returns the Popen handle, or None when falling
    back to webbrowser.open() (no Chromium-based browser found).
    """
    exe = _find_chromium_exe()
    if exe is None:
        import webbrowser
        webbrowser.open(url)
        return None

    BROWSER_PROFILE.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [
            str(exe),
            f"--user-data-dir={BROWSER_PROFILE}",
            "--no-first-run",
            "--no-default-browser-check",
            "--new-window",
            url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc


def _kill_browser(proc: "subprocess.Popen[bytes]") -> None:
    """Terminate the browser process tree."""
    if proc.poll() is not None:
        return  # Already exited (e.g. user closed it manually)
    if sys.platform == "win32":
        # /T kills the whole process tree (GPU, renderer, … children)
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        proc.terminate()


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

    browser_proc: "subprocess.Popen[bytes] | None" = None
    if not args.no_browser:
        browser_proc = _launch_browser(url)

    import uvicorn
    from pressroom.api.app import create_app

    print(f"\nStarting Pressroom at {url}")
    print("Press Ctrl-C to stop.\n")
    try:
        uvicorn.run(create_app(), host=args.host, port=args.port)
    finally:
        if browser_proc is not None:
            _kill_browser(browser_proc)


if __name__ == "__main__":
    main()
