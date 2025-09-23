#!/usr/bin/env python3
"""GitHub-based auto-updater for Whisper PGE."""
from __future__ import annotations

import argparse
import json
import os
import importlib
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any


def ensure_runtime_dependencies() -> None:
    pip_sets = [
        {
            "modules": ["requests", "packaging"],
            "packages": ["requests>=2.31.0", "packaging>=23.2"],
        },
        {
            "modules": ["psutil"],
            "packages": ["psutil>=5.9.0"],
        },
    ]

    log_root = Path(os.getenv("LOCALAPPDATA", Path.home())) / "WhisperPGE" / "logs"
    log_root.mkdir(parents=True, exist_ok=True)
    log_file = log_root / "bootstrap.log"

    def log(message: str) -> None:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{stamp}] {message}\n"
        print(line, end="")
        try:
            with log_file.open("a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception:
            pass

    for bundle in pip_sets:
        missing = []
        for module in bundle["modules"]:
            try:
                __import__(module)
            except ImportError:
                missing.append(module)
        if not missing:
            continue

        log(f"Dependências do updater ausentes ({', '.join(missing)}). Instalando {bundle['packages']}...")
        args = ["install", "--upgrade"]
        args.extend(bundle.get("options", []))
        args.extend(bundle["packages"])
        try:
            from pip._internal.cli.main import main as pip_main

            result = pip_main(args)
            if result != 0:
                raise RuntimeError(f"pip returned {result}")

            importlib.invalidate_caches()
            for module in bundle["modules"]:
                try:
                    __import__(module)
                except ImportError:
                    raise RuntimeError(f"Falha ao importar {module} após instalação")

            log(f"Instalação concluída: {bundle['packages']}")
        except Exception as exc:
            log(f"Falha ao instalar {bundle['packages']}: {exc}")
            raise


ensure_runtime_dependencies()

import requests
from packaging.version import Version

try:
    import winreg  # type: ignore
except ImportError:  # pragma: no cover - non-Windows platforms
    winreg = None  # type: ignore

try:
    import tkinter as tk
    from tkinter import messagebox
except Exception:  # pragma: no cover - headless environments
    tk = None  # type: ignore
    messagebox = None  # type: ignore

REPO_OWNER = "kaoyeoshiro"
REPO_NAME = "whisper_PGE"
ASSET_NAME = "WhisperPGE.exe"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "WhisperPGE-Updater"
USER_AGENT = "WhisperPGE-Updater"


def get_install_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_version_file() -> Path:
    return get_install_root() / "app" / "version.json"


def ensure_log_file() -> Path:
    local_app = Path(os.getenv("LOCALAPPDATA", get_install_root()))
    log_dir = local_app / "WhisperPGE" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "updater.log"


LOG_PATH = ensure_log_file()


def log(message: str) -> None:
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass  # Logging failures are non-fatal


def read_local_version() -> Version:
    version_file = get_version_file()
    if not version_file.exists():
        return Version("0.0.0")
    try:
        data = json.loads(version_file.read_text(encoding="utf-8"))
        return Version(str(data.get("version", "0.0.0")))
    except Exception as exc:
        log(f"Failed to parse local version: {exc}")
        return Version("0.0.0")


def write_local_version(new_version: Version) -> None:
    version_file = get_version_file()
    version_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": str(new_version)}
    version_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def ensure_autostart(command: str) -> None:
    if winreg is None:
        log("winreg unavailable; skipping auto-start registration")
        return

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            try:
                current, _ = winreg.QueryValueEx(key, RUN_VALUE_NAME)
            except FileNotFoundError:
                current = None
            if current != command:
                winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, command)
                log("Registered updater in HKCU Run key")
            else:
                log("Auto-start already registered")
    except PermissionError as exc:
        log(f"Failed to register auto-start (permission error): {exc}")


def request_latest_release() -> dict[str, Any]:
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
    response.raise_for_status()
    return response.json()


def parse_remote_version(release: dict[str, Any]) -> Version:
    tag = str(release.get("tag_name", "")).strip()
    if not tag:
        raise ValueError("Release tag missing")
    if tag.lower().startswith("v"):
        tag = tag[1:]
    return Version(tag)


def find_asset_url(release: dict[str, Any]) -> str:
    assets = release.get("assets", [])
    for asset in assets:
        if asset.get("name") == ASSET_NAME:
            return str(asset.get("browser_download_url"))
    raise ValueError(f"Asset {ASSET_NAME} not found in release")


def ask_user_to_update(current_version: Version, new_version: Version) -> bool:
    if messagebox is None:
        return True
    root = tk.Tk()
    root.withdraw()
    try:
        return messagebox.askyesno(
            "Whisper PGE",
            f"Nova versão disponível: {new_version} (atual: {current_version}).\nDeseja atualizar agora?",
            icon="info",
        )
    finally:
        root.destroy()


def show_info(message: str) -> None:
    if messagebox is None:
        return
    root = tk.Tk()
    root.withdraw()
    try:
        messagebox.showinfo("Whisper PGE", message)
    finally:
        root.destroy()


def download_asset(url: str) -> Path:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30, stream=True)
    response.raise_for_status()

    fd, temp_path = tempfile.mkstemp(suffix=".exe")
    with os.fdopen(fd, "wb") as handle:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                handle.write(chunk)
    return Path(temp_path)


def stop_running_instances(executable: Path) -> None:
    exe_name = executable.name
    try:
        subprocess.run(["taskkill", "/IM", exe_name, "/F"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        log("taskkill not available; skipping process termination")


def apply_update(temp_file: Path, target_exe: Path, new_version: Version) -> None:
    stop_running_instances(target_exe)
    target_exe.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(temp_file, target_exe)
    write_local_version(new_version)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Whisper PGE updater")
    parser.add_argument("--silent", action="store_true", help="Suprime mensagens quando não há atualização")
    parser.add_argument("--force", action="store_true", help="Instala mesmo se versões forem iguais")
    args = parser.parse_args(argv)

    if getattr(sys, "frozen", False):
        executable_path = Path(sys.executable).resolve()
        autostart_command = f'"{executable_path}" --silent'
    else:
        script_path = Path(__file__).resolve()
        autostart_command = f'"{sys.executable}" "{script_path}" --silent'
    ensure_autostart(autostart_command)

    try:
        local_version = read_local_version()
        log(f"Local version: {local_version}")

        release = request_latest_release()
        remote_version = parse_remote_version(release)
        log(f"Remote version: {remote_version}")

        if not args.force and remote_version <= local_version:
            log("No update required")
            if not args.silent:
                show_info("Você já está usando a versão mais recente do Whisper PGE.")
            return 0

        asset_url = find_asset_url(release)
        if args.silent:
            user_agreed = True
        else:
            user_agreed = ask_user_to_update(local_version, remote_version)
        if not user_agreed:
            log("User deferred update")
            return 0

        log(f"Downloading update from {asset_url}")
        temp_file = download_asset(asset_url)
        try:
            target_exe = get_install_root() / ASSET_NAME
            apply_update(temp_file, target_exe, remote_version)
            log("Update applied successfully")
            if not args.silent:
                show_info(f"Whisper PGE foi atualizado para a versão {remote_version}.")
        finally:
            temp_file.unlink(missing_ok=True)
        return 0
    except Exception as exc:
        log(f"Update failed: {exc}")
        if not args.silent:
            show_info("Falha ao verificar ou aplicar atualização. Veja o log para detalhes.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
