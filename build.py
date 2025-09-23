#!/usr/bin/env python3
"""Build automation for WhisperPGE Installer using PyInstaller."""

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
PYI_BUILD_DIR = PROJECT_ROOT / ".pyinstaller-build"
VERSION_FILE = PROJECT_ROOT / "app" / "version.json"


def run(cmd: list[str]) -> None:
    subprocess.check_call(cmd)


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        run([sys.executable, "-m", "pip", "install", "pyinstaller"])


def clean_previous_artifacts() -> None:
    for path in (DIST_DIR, PYI_BUILD_DIR):
        if path.exists():
            shutil.rmtree(path)
    BUILD_DIR.mkdir(exist_ok=True)


def copy_support_files() -> None:
    target_version = BUILD_DIR / "app" / "version.json"
    target_version.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(VERSION_FILE, target_version)


def main() -> None:
    ensure_pyinstaller()
    clean_previous_artifacts()

    print("[build] Building WhisperPGE-Installer.exe")
    launcher_spec = PROJECT_ROOT / "launcher_optimized.spec"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(PYI_BUILD_DIR),
        str(launcher_spec)
    ]
    run(cmd)

    # Move executable to build directory
    launcher_exe = DIST_DIR / "WhisperPGE-Installer.exe"
    if launcher_exe.exists():
        shutil.move(str(launcher_exe), BUILD_DIR / "WhisperPGE-Installer.exe")

    copy_support_files()

    # Clean temporary directories
    for path in (DIST_DIR, PYI_BUILD_DIR):
        if path.exists():
            shutil.rmtree(path)

    print(f"[build] WhisperPGE-Installer.exe available in {BUILD_DIR}")


if __name__ == "__main__":
    main()