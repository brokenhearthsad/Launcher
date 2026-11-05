"""Locate Steam, its libraries and Dota 2 (app 570) from registry and Steam's own files.

Read-only. No Steam credentials are read or stored: from the registry only the
install path, the Steam process id and a *signed-in yes/no* flag are used.
"""
from __future__ import annotations

import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.integrations.vdf import VdfError, get_ci, loads

DOTA_APP_ID = "570"
DOTA_EXE = Path("game") / "bin" / "win64" / "dota2.exe"
DEFAULT_STEAM_DIRS = [Path(r"C:\Program Files (x86)\Steam"), Path(r"C:\Program Files\Steam")]

# Steam EAppState bit flags (appmanifest "StateFlags").
STATE_FLAGS = {
    1: "uninstalled", 2: "update_required", 4: "fully_installed", 8: "encrypted", 16: "locked",
    32: "files_missing", 64: "app_running", 128: "files_corrupt", 256: "update_running", 512: "update_paused",
    1024: "update_started", 2048: "uninstalling", 4096: "backup_running", 65536: "reconfiguring",
    131072: "validating", 262144: "adding_files", 524288: "preallocating", 1048576: "downloading",
    2097152: "staging", 4194304: "committing", 8388608: "update_stopping",
}


def decode_state_flags(flags: int) -> list[str]:
    return [name for bit, name in STATE_FLAGS.items() if flags & bit]


# ----------------------------------------------------------------------------- registry
def read_registry() -> dict[str, Any]:
    """Steam values from the Windows registry ({} on other platforms or if absent)."""
    if sys.platform != "win32":
        return {}
    import winreg

    out: dict[str, Any] = {}

    def read(root, path: str, name: str):
        try:
            with winreg.OpenKey(root, path) as k:
                return winreg.QueryValueEx(k, name)[0]
        except OSError:
            return None

    hkcu, hklm = winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE
    out["steam_path"] = read(hkcu, r"Software\Valve\Steam", "SteamPath")
    out["install_path"] = (read(hklm, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")
                           or read(hklm, r"SOFTWARE\Valve\Steam", "InstallPath"))
    out["active_pid"] = read(hkcu, r"Software\Valve\Steam\ActiveProcess", "pid")
    active_user = read(hkcu, r"Software\Valve\Steam\ActiveProcess", "ActiveUser")
    out["signed_in"] = None if active_user is None else bool(active_user)
    return {k: v for k, v in out.items() if v is not None}


# ----------------------------------------------------------------------------- discovery
@dataclass
class SteamInstall:
    installed: bool
    path: str | None = None
    source: str | None = None  # config | registry | default
    libraries: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class DotaInstall:
    installed: bool
    path: str | None = None
    library: str | None = None
    exe_exists: bool = False
    buildid: str | None = None
    state_flags: int | None = None
    state: list[str] = field(default_factory=list)
    last_updated: str | None = None
    size_gb: float | None = None
    error: str | None = None


def find_steam(override: Path | None, registry: dict[str, Any]) -> SteamInstall:
    candidates: list[tuple[str, Path]] = []
    if override:
        candidates.append(("config", Path(override)))
    for key in ("steam_path", "install_path"):
        if registry.get(key):
            candidates.append(("registry", Path(str(registry[key]))))
    if sys.platform == "win32":
        candidates += [("default", p) for p in DEFAULT_STEAM_DIRS]
    for source, path in candidates:
        if (path / "steamapps").is_dir() or (path / "steam.exe").is_file():
            libs, err = libraries(path)
            return SteamInstall(True, str(path), source, libs, err)
    return SteamInstall(False, error="Steam installation not found (registry and default folders checked)")


def libraries(steam_path: Path) -> tuple[list[str], str | None]:
    """All Steam library folders, the Steam folder itself first."""
    result = [str(steam_path)]
    vdf_path = steam_path / "steamapps" / "libraryfolders.vdf"
    if not vdf_path.is_file():
        return result, None
    try:
        data = loads(vdf_path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, VdfError) as exc:
        return result, f"cannot read libraryfolders.vdf: {exc}"
    root = get_ci(data, "libraryfolders") or get_ci(data, "LibraryFolders") or {}
    for key, value in root.items():
        if not key.isdigit():
            continue
        path = get_ci(value, "path") if isinstance(value, dict) else value  # new / old format
        if path and str(Path(path)) not in {str(Path(p)) for p in result}:
            result.append(str(Path(path)))
    return result, None


def find_dota(libs: list[str]) -> DotaInstall:
    for lib in libs:
        manifest = Path(lib) / "steamapps" / f"appmanifest_{DOTA_APP_ID}.acf"
        if not manifest.is_file():
            continue
        try:
            app = get_ci(loads(manifest.read_text(encoding="utf-8", errors="replace")), "AppState") or {}
        except (OSError, VdfError) as exc:
            return DotaInstall(False, library=lib, error=f"cannot read {manifest.name}: {exc}")
        installdir = get_ci(app, "installdir") or "dota 2 beta"
        game_dir = Path(lib) / "steamapps" / "common" / installdir
        flags = int(get_ci(app, "StateFlags") or 0)
        updated = get_ci(app, "LastUpdated")
        size = get_ci(app, "SizeOnDisk")
        return DotaInstall(
            installed=True, path=str(game_dir), library=lib, exe_exists=(game_dir / DOTA_EXE).is_file(),
            buildid=get_ci(app, "buildid"), state_flags=flags, state=decode_state_flags(flags),
            last_updated=(datetime.fromtimestamp(int(updated), tz=timezone.utc).isoformat()
                          if updated and str(updated).isdigit() else None),
            size_gb=round(int(size) / 1e9, 1) if size and str(size).isdigit() else None,
        )
    return DotaInstall(False, error="appmanifest_570.acf not found in any Steam library")


def discover(override: Path | None) -> dict[str, Any]:
    reg = read_registry()
    steam = find_steam(override, reg)
    dota = find_dota(steam.libraries) if steam.installed else DotaInstall(False, error="Steam not found")
    return {"steam": asdict(steam), "dota": asdict(dota), "signed_in": reg.get("signed_in"),
            "registry_available": bool(reg), "platform": sys.platform}
