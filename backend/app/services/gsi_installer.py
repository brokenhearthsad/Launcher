"""Safe install / update / removal of Launcher's GSI configuration file.

Rules:
* Only ``<Dota 2>/game/dota/cfg/gamestate_integration/gamestate_integration_launcher.cfg``
  is ever written or deleted; other ``gamestate_integration_*.cfg`` files are listed, never touched.
* Every change is a two-step operation: the client first reads a *plan*
  (``plan_id`` = hash of the current file + new content) and must send it
  back with ``confirm=true``. If the file changed in between, nothing happens.
* An existing file is copied to ``backend/data/gsi_backups`` before it is
  replaced, removed or restored over. Backups are never deleted by Launcher.
* Removal is allowed only for a file created by Launcher (marker comment).
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from app.errors import AppError, ConflictError, NotFoundError, ValidationFailed
from app.integrations.vdf import VdfError, get_ci, loads
from app.logging_config import get_logger
from app.services import events

log = get_logger("gsi.installer")
CFG_NAME = "gamestate_integration_launcher.cfg"
MARKER = "// Managed by Launcher"
BACKUP_RE = re.compile(r"^\d{8}-\d{6}(-\d+)?-[a-z_]+\.cfg$")


class GsiInstallError(AppError):
    status_code = 409
    code = "gsi_install_error"


def render(token: str, port: int) -> str:
    return f'''{MARKER} (read-only Game State Integration). Remove it from Launcher > "Состояние игры".
// Dota 2 sends game state to Launcher on this computer only. Launcher never sends commands to the game.
"Launcher GSI"
{{
	"uri"		"http://127.0.0.1:{port}/gsi"
	"timeout"	"5.0"
	"buffer"	"0.1"
	"throttle"	"0.5"
	"heartbeat"	"30.0"
	"data"
	{{
		"provider"	"1"
		"map"		"1"
		"player"	"1"
		"hero"		"1"
		"abilities"	"1"
		"items"		"1"
	}}
	"auth"
	{{
		"token"		"{token}"
	}}
}}
'''


def _sha(text: str | None) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


class GsiInstaller:
    def __init__(self, state: Any):
        self.state = state
        self.backup_dir: Path = Path(state.config.backup_dir).parent / "gsi_backups"

    # ------------------------------------------------------------------ discovery
    def _dota_path(self) -> Path | None:
        env = self.state.environment
        snap = env.snapshot() if env is not None and env.polled_at else None
        if not snap or not snap["dota"].get("installed") or not snap["dota"].get("path"):
            return None
        return Path(snap["dota"]["path"])

    def target(self) -> tuple[Path | None, str | None]:
        dota = self._dota_path()
        if dota is None:
            return None, "Dota 2 не найдена (см. раздел «Steam и Dota 2»)"
        game_dir = dota / "game" / "dota"
        if not game_dir.is_dir():
            return None, f"папка {game_dir} не найдена — установка Dota 2 повреждена или не завершена"
        return game_dir / "cfg" / "gamestate_integration" / CFG_NAME, None

    def _mask(self, text: str | None) -> str | None:
        if text is None:
            return None
        token = self.state.gsi.token
        return text.replace(token, "•" * 8 + token[-4:]) if token else text

    def _read(self, path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return None

    def _inspect(self, text: str | None) -> dict[str, Any]:
        if text is None:
            return {"managed": False, "valid": None, "uri": None, "token_matches": None}
        try:
            data = loads(text)
            block = next(iter(data.values())) if data else {}
            uri = get_ci(block, "uri") if isinstance(block, dict) else None
            auth = get_ci(block, "auth") if isinstance(block, dict) else None
            token = get_ci(auth, "token") if isinstance(auth, dict) else None
            valid = True
        except VdfError:
            uri = token = None
            valid = False
        return {"managed": text.lstrip().startswith(MARKER), "valid": valid, "uri": uri,
                "token_matches": token == self.state.gsi.token if token is not None else False}

    # ------------------------------------------------------------------ check / plan
    def check(self) -> dict[str, Any]:
        path, error = self.target()
        out: dict[str, Any] = {"cfg_name": CFG_NAME, "error": error, "backups": self.backups(),
                               "launch_option": self.launch_option()}
        if path is None:
            out.update({"available": False, "installed": False, "plan": None})
            return out
        current = self._read(path)
        new = render(self.state.gsi.token, self.state.config.port)
        info = self._inspect(current)
        expected_uri = f"http://127.0.0.1:{self.state.config.port}/gsi"
        up_to_date = current is not None and current == new
        others = sorted(p.name for p in path.parent.glob("gamestate_integration_*.cfg") if p.name != CFG_NAME) \
            if path.parent.is_dir() else []
        if current is None:
            action = "create"
        elif up_to_date:
            action = "none"
        elif info["managed"]:
            action = "update"
        else:
            action = "replace_foreign"
        out.update({
            "available": True, "file": str(path), "dir_exists": path.parent.is_dir(), "exists": current is not None,
            "installed": current is not None and info["managed"] and info["token_matches"] and info["uri"] == expected_uri,
            "up_to_date": up_to_date, **info, "expected_uri": expected_uri, "other_configs": others,
            "plan": {
                "action": action, "plan_id": _sha(current) + _sha(new),
                "creates_directory": not path.parent.is_dir(),
                "backup_before_change": current is not None,
                "current_content": self._mask(current), "new_content": self._mask(new),
            },
        })
        return out

    # ------------------------------------------------------------------ actions
    def _backup(self, path: Path, label: str) -> Path:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = self.backup_dir / f"{stamp}-{label}.cfg"
        n = 1
        while dest.exists():
            dest = self.backup_dir / f"{stamp}-{n}-{label}.cfg"
            n += 1
        shutil.copy2(path, dest)
        return dest

    @staticmethod
    def _atomic_write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".cfg.tmp")
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp, path)

    def install(self, plan_id: str, confirm: bool) -> dict[str, Any]:
        if not confirm:
            raise ValidationFailed("установка требует явного подтверждения (confirm=true)")
        path, error = self.target()
        if path is None:
            raise GsiInstallError(error or "Dota 2 не найдена")
        current = self._read(path)
        new = render(self.state.gsi.token, self.state.config.port)
        if plan_id != _sha(current) + _sha(new):
            raise ConflictError("файл конфигурации изменился после предпросмотра — "
                                "обновите страницу и проверьте изменения снова")
        if current == new:
            return {"changed": False, "backup": None, "check": self.check()}
        backup = self._backup(path, "before_install") if current is not None else None
        self._atomic_write(path, new)
        what = "обновлена" if current is not None else "установлена"
        events.record(self.state.bus, "gsi", "config_installed", f"Конфигурация GSI {what}: {path}",
                      data={"file": str(path), "backup": backup.name if backup else None})
        return {"changed": True, "backup": backup.name if backup else None, "check": self.check()}

    def uninstall(self, confirm: bool) -> dict[str, Any]:
        if not confirm:
            raise ValidationFailed("удаление требует явного подтверждения (confirm=true)")
        path, error = self.target()
        if path is None:
            raise GsiInstallError(error or "Dota 2 не найдена")
        current = self._read(path)
        if current is None:
            raise NotFoundError("конфигурация Launcher не установлена")
        if not self._inspect(current)["managed"]:
            raise GsiInstallError("файл создан не Launcher — удалять его Launcher не будет")
        backup = self._backup(path, "before_uninstall")
        path.unlink()
        events.record(self.state.bus, "gsi", "config_removed", f"Конфигурация GSI удалена (копия: {backup.name})",
                      data={"file": str(path), "backup": backup.name})
        return {"removed": True, "backup": backup.name, "check": self.check()}

    def backups(self) -> list[dict[str, Any]]:
        if not self.backup_dir.is_dir():
            return []
        out = []
        for p in sorted(self.backup_dir.glob("*.cfg"), reverse=True):
            if not BACKUP_RE.match(p.name):
                continue
            text = self._read(p) or ""
            out.append({"name": p.name, "size": p.stat().st_size,
                        "created": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                        "managed": text.lstrip().startswith(MARKER)})
        return out

    def restore(self, name: str, confirm: bool) -> dict[str, Any]:
        if not confirm:
            raise ValidationFailed("восстановление требует явного подтверждения (confirm=true)")
        if not BACKUP_RE.match(name):
            raise ValidationFailed("недопустимое имя резервной копии")
        src = self.backup_dir / name
        if not src.is_file():
            raise NotFoundError(f"резервная копия {name} не найдена")
        path, error = self.target()
        if path is None:
            raise GsiInstallError(error or "Dota 2 не найдена")
        current_backup = self._backup(path, "before_restore") if path.exists() else None
        self._atomic_write(path, src.read_text(encoding="utf-8", errors="replace"))
        events.record(self.state.bus, "gsi", "config_restored", f"Конфигурация GSI восстановлена из {name}",
                      data={"file": str(path), "from": name,
                            "backup": current_backup.name if current_backup else None})
        return {"restored": name, "backup": current_backup.name if current_backup else None, "check": self.check()}

    # ------------------------------------------------------------------ launch option (read-only)
    def launch_option(self) -> dict[str, Any]:
        """Whether ``-gamestateintegration`` is in Dota 2 launch options (Steam userdata, read-only)."""
        env = self.state.environment
        snap = env.snapshot() if env is not None and env.polled_at else None
        steam = snap["steam"].get("path") if snap else None
        if not steam:
            return {"checked": False, "found": None, "accounts": 0}
        files = list((Path(steam) / "userdata").glob("*/config/localconfig.vdf"))
        found_any = False
        checked = 0
        for f in files[:8]:
            try:
                data = loads(f.read_text(encoding="utf-8", errors="replace"))
            except (OSError, VdfError):
                continue
            node: Any = data
            for key in ("UserLocalConfigStore", "Software", "Valve", "Steam", "apps", "570"):
                node = get_ci(node, key) if isinstance(node, dict) else None
            checked += 1
            opts = get_ci(node, "LaunchOptions", "") if isinstance(node, dict) else ""
            if "-gamestateintegration" in str(opts).lower():
                found_any = True
        return {"checked": checked > 0, "found": found_any if checked else None, "accounts": checked}
