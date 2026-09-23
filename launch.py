"""Small, standard-library-only launcher for AFTERBURN."""

from __future__ import annotations

import contextlib
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parent
ENVIRONMENT = ROOT / ".venv"
PYTHON = ENVIRONMENT / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
REQUIREMENTS = ROOT / "requirements.txt"
STAMP = ENVIRONMENT / ".afterburn-requirements"


@contextlib.contextmanager
def setup_lock():
    """Keep simultaneous first-run launchers from installing over each other."""
    lock_path = ROOT / ".afterburn-setup.lock"
    with lock_path.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        waiting = False
        while True:
            handle.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (OSError, BlockingIOError):
                if not waiting:
                    print("Another AFTERBURN window is setting up. Waiting...", flush=True)
                    waiting = True
                time.sleep(1)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def dependencies_import():
    if not PYTHON.is_file():
        return False
    try:
        result = subprocess.run(
            [str(PYTHON), "-c", "import numpy, PIL, moderngl, glcontext, imageio_ffmpeg"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=45,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def ensure_runtime():
    fingerprint = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    with setup_lock():
        if STAMP.is_file() and STAMP.read_text(encoding="utf-8").strip() == fingerprint:
            if dependencies_import():
                return

        print("\nPreparing AFTERBURN's private Python environment...", flush=True)
        print("First setup needs internet. Your music stays on this computer.\n", flush=True)
        if not PYTHON.is_file():
            subprocess.run(
                [sys.executable, "-m", "venv", str(ENVIRONMENT)],
                check=True,
            )

        subprocess.run(
            [
                str(PYTHON), "-m", "pip", "--disable-pip-version-check", "install",
                "--no-input", "-r", str(REQUIREMENTS),
            ],
            check=True,
        )
        if not dependencies_import():
            raise RuntimeError("The rendering libraries could not load after installation.")
        STAMP.write_text(fingerprint + "\n", encoding="utf-8")
        print("\nSetup complete. Starting the renderer...\n", flush=True)


def main():
    if sys.version_info < (3, 11):
        print("AFTERBURN needs Python 3.11 or newer. Install Python, then try again.")
        return 1
    try:
        ensure_runtime()
        # An argument list preserves spaces, punctuation, and Unicode in song paths.
        # Do not turn this into a shell command or call the bootstrap recursively.
        return subprocess.run(
            [str(PYTHON), "-u", str(ROOT / "afterburn.py"), *sys.argv[1:]],
            check=False,
        ).returncode
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
        return 130
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"\nAFTERBURN could not start: {error}", file=sys.stderr, flush=True)
        print(
            "Check your internet connection for first setup and extract the full folder "
            "somewhere you can write files. Then run the launcher again.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
