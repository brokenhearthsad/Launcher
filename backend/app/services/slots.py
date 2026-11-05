"""Ten logical slots.

A slot is a label + note, optionally bound to the local Steam / Dota 2 client
(``binding = local_client``) so its status reflects what is really running on
this PC. Only one slot can be bound: one Windows user runs one Steam client.
Slots never start games, log in, or control matches.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ClientSlot, Event
from app.db.session import session_scope
from app.errors import ConflictError, NotFoundError
from app.services import events

BINDINGS = ("none", "local_client")
STATUS_LABELS = {
    "unbound": "Не привязан",
    "steam_not_installed": "Steam не найден",
    "steam_stopped": "Steam не запущен",
    "steam_running": "Steam запущен",
    "dota_running": "Dota 2 запущена",
}


def compute_status(binding: str, env: dict[str, Any] | None) -> str:
    if binding != "local_client":
        return "unbound"
    if env is None or not env["steam"].get("installed"):
        return "steam_not_installed"
    if env["dota"]["process"].get("running"):
        return "dota_running"
    if env["steam"]["process"].get("running"):
        return "steam_running"
    return "steam_stopped"


def _view(slot: ClientSlot, env: dict[str, Any] | None) -> dict[str, Any]:
    status = compute_status(slot.binding, env)
    out = {"id": slot.id, "name": slot.name, "note": slot.note, "team": slot.team, "binding": slot.binding,
           "status": status, "status_label": STATUS_LABELS[status], "updated_at": slot.updated_at.isoformat()}
    if slot.binding == "local_client" and env is not None:
        out["observed"] = {"steam_pid": env["steam"]["process"].get("pid"),
                           "dota_pid": env["dota"]["process"].get("pid"),
                           "signed_in": env["steam"].get("signed_in")}
    return out


class SlotService:
    def __init__(self, state: Any):
        self.state = state
        self._last: dict[int, str] = {}
        with session_scope() as db:
            for slot in db.scalars(select(ClientSlot)):
                last = db.scalars(select(Event).where(Event.slot_id == slot.id, Event.type == "status_changed")
                                  .order_by(Event.id.desc()).limit(1)).first()
                self._last[slot.id] = (last.data or {}).get("to") if last else compute_status(slot.binding, None)

    def env(self) -> dict[str, Any] | None:
        env = self.state.environment
        return env.snapshot() if env is not None and env.polled_at else None

    def list(self, db: Session) -> list[dict[str, Any]]:
        env = self.env()
        return [_view(s, env) for s in db.scalars(select(ClientSlot).order_by(ClientSlot.id))]

    def get(self, db: Session, slot_id: int) -> dict[str, Any]:
        return _view(self._slot(db, slot_id), self.env())

    def _slot(self, db: Session, slot_id: int) -> ClientSlot:
        slot = db.get(ClientSlot, slot_id)
        if slot is None:
            raise NotFoundError(f"slot {slot_id} not found")
        return slot

    def update(self, db: Session, slot_id: int, changes: dict[str, Any]) -> dict[str, Any]:
        slot = self._slot(db, slot_id)
        notes: list[tuple[str, str, dict[str, Any]]] = []
        if "binding" in changes and changes["binding"] != slot.binding:
            if changes["binding"] == "local_client":
                other = db.scalars(select(ClientSlot).where(ClientSlot.binding == "local_client",
                                                            ClientSlot.id != slot_id)).first()
                if other is not None:
                    raise ConflictError(f"локальный клиент уже привязан к слоту «{other.name}» (#{other.id}); "
                                        "сначала отвяжите его — на одном ПК работает только один клиент Steam")
                notes.append(("bound", "Привязан к локальному клиенту", {}))
            else:
                notes.append(("unbound", "Привязка к локальному клиенту снята", {}))
            slot.binding = changes["binding"]
        if "name" in changes and changes["name"] != slot.name:
            notes.append(("renamed", f"Переименован: «{slot.name}» → «{changes['name']}»",
                          {"from": slot.name, "to": changes["name"]}))
            slot.name = changes["name"]
        if "note" in changes and changes["note"] != slot.note:
            notes.append(("note_changed", "Заметка изменена", {}))
            slot.note = changes["note"]
        db.commit()
        db.refresh(slot)
        for type_, message, data in notes:
            events.record(self.state.bus, "slot", type_, message, data=data, slot_id=slot_id)
        self.observe(self.env())
        view = _view(slot, self.env())
        self.state.bus.publish("slot_updated", view)
        return view

    def observe(self, env: dict[str, Any] | None) -> None:
        """Record status transitions of slots (called when the environment changes)."""
        with session_scope() as db:
            slots = list(db.scalars(select(ClientSlot)))
        for slot in slots:
            status = compute_status(slot.binding, env)
            prev = self._last.get(slot.id)
            if status != prev:
                self._last[slot.id] = status
                events.record(self.state.bus, "slot", "status_changed",
                              f"Статус: {STATUS_LABELS.get(prev or '', prev or '—')} → {STATUS_LABELS[status]}",
                              data={"from": prev, "to": status}, slot_id=slot.id)
                self.state.bus.publish("slot_updated", _view(slot, env))
