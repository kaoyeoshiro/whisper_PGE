
#!/usr/bin/env python3
"""Lightweight build automation for Whisper PGE executables."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
PYI_BUILD_DIR = PROJECT_ROOT / ".pyinstaller-build"
PYI_SPEC_DIR = PROJECT_ROOT / ".pyinstaller-spec"
VERSION_FILE = PROJECT_ROOT / "app" / "version.json"

MAIN_ENTRY = PROJECT_ROOT / "main.py"
UPDATER_ENTRY = PROJECT_ROOT / "updater.py"


def run(cmd: list[str]) -> None:
    subprocess.check_call(cmd)


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        run([sys.executable, "-m", "pip", "install", "pyinstaller"])


def clean_previous_artifacts() -> None:
    for path in (DIST_DIR, PYI_BUILD_DIR, PYI_SPEC_DIR):
        if path.exists():
            shutil.rmtree(path)
    BUILD_DIR.mkdir(exist_ok=True)


def build_executable(entry: Path, name: str, add_data: list[tuple[Path, str]] | None = None) -> Path:
    if not entry.exists():
        raise FileNotFoundError(f"Entry point not found: {entry}")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        name,
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(PYI_BUILD_DIR),
        "--specpath",
        str(PYI_SPEC_DIR),
    ]

    if add_data:
        for source, target in add_data:
            cmd.extend(["--add-data", f"{source}{os.pathsep}{target}"])

    cmd.append(str(entry))
    run(cmd)

    built_path = DIST_DIR / f"{name}.exe"
    if not built_path.exists():
        raise FileNotFoundError(f"Expected artifact missing: {built_path}")

    destination = BUILD_DIR / built_path.name
    shutil.move(str(built_path), destination)
    return destination


def copy_support_files() -> None:
    target_version = BUILD_DIR / "app" / "version.json"
    target_version.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(VERSION_FILE, target_version)


def main() -> None:
    ensure_pyinstaller()
    clean_previous_artifacts()

    print("[build] Building WhisperPGE.exe")
    build_executable(
        entry=MAIN_ENTRY,
        name="WhisperPGE",
        add_data=[(VERSION_FILE, "app/version.json")],
    )

    print("[build] Building updater.exe")
    build_executable(
        entry=UPDATER_ENTRY,
        name="updater",
    )

    copy_support_files()

    for path in (DIST_DIR, PYI_BUILD_DIR, PYI_SPEC_DIR):
        if path.exists():
            shutil.rmtree(path)

    print(f"[build] Artifacts available in {BUILD_DIR}")


if __name__ == "__main__":
    main()
