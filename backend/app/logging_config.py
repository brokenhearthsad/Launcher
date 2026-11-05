"""Structured JSON logging.

Every log record is written as one JSON object per line to stdout and to a
rotating file. Records from application loggers (``dml.*``) at or above the
configured DB level are additionally persisted to the ``system_logs`` table
by a background thread, so the request path never waits for SQLite.
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import queue
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

ROOT_LOGGER = "dml"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "component": component_of(record),
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "data", None)
        if extra:
            payload["data"] = extra
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def component_of(record: logging.LogRecord) -> str:
    name = record.name
    if name.startswith(ROOT_LOGGER + "."):
        return name[len(ROOT_LOGGER) + 1 :]
    return name


class DatabaseLogHandler(logging.Handler):
    """Queues records; a daemon thread writes them in batches via ``sink``."""

    def __init__(self, sink: Callable[[list[dict]], None], level: int = logging.INFO):
        super().__init__(level)
        self._sink = sink
        self._queue: queue.Queue[dict | None] = queue.Queue(maxsize=10_000)
        self._thread = threading.Thread(target=self._run, name="db-log-writer", daemon=True)
        self._thread.start()

    def emit(self, record: logging.LogRecord) -> None:
        if not record.name.startswith(ROOT_LOGGER):
            return
        if record.name.startswith(f"{ROOT_LOGGER}.db_log"):
            return  # never log about logging into the DB (recursion guard)
        message = record.getMessage()
        if record.exc_info and record.exc_info[1] is not None:
            message = f"{message} | {type(record.exc_info[1]).__name__}: {record.exc_info[1]}"
        item = {
            "level": record.levelname,
            "component": component_of(record),
            "message": message[:4000],
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc),
        }
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            pass  # dropping logs is preferable to blocking the simulator

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            batch = [item]
            while len(batch) < 200:
                try:
                    nxt = self._queue.get_nowait()
                except queue.Empty:
                    break
                if nxt is None:
                    self._write(batch)
                    return
                batch.append(nxt)
            self._write(batch)

    def _write(self, batch: list[dict]) -> None:
        try:
            self._sink(batch)
        except Exception:  # noqa: BLE001 - must never crash the writer
            logging.getLogger(f"{ROOT_LOGGER}.db_log").exception("failed to persist logs")

    def flush(self, timeout: float = 2.0) -> None:
        """Best effort: wait until the queue is drained (used by tests/shutdown)."""
        import time

        deadline = time.monotonic() + timeout
        while not self._queue.empty() and time.monotonic() < deadline:
            time.sleep(0.01)
        time.sleep(0.05)

    def close(self) -> None:
        # ``logging.config.dictConfig`` and ``logging.shutdown`` call close() on every
        # handler. Only flush here; the writer thread is stopped explicitly by stop().
        self.flush(timeout=1.0)
        super().close()

    def stop(self) -> None:
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        self._thread.join(timeout=2.0)


_db_handler: DatabaseLogHandler | None = None


def setup_logging(level: str, log_dir: Path) -> None:
    root = logging.getLogger(ROOT_LOGGER)
    root.setLevel(level.upper())
    root.propagate = False
    for h in list(root.handlers):
        if not isinstance(h, DatabaseLogHandler):
            root.removeHandler(h)
    formatter = JsonFormatter()
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    root.addHandler(stream)
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "app.jsonl", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        root.warning("file logging disabled: cannot write to %s", log_dir)


def install_db_handler(sink: Callable[[list[dict]], None], level: str) -> DatabaseLogHandler:
    global _db_handler
    root = logging.getLogger(ROOT_LOGGER)
    if _db_handler is not None:
        root.removeHandler(_db_handler)
        _db_handler.stop()
    _db_handler = DatabaseLogHandler(sink, logging.getLevelName(level.upper()))
    root.addHandler(_db_handler)
    return _db_handler


def get_db_handler() -> DatabaseLogHandler | None:
    return _db_handler


def set_levels(log_level: str | None = None, db_log_level: str | None = None) -> None:
    if log_level:
        logging.getLogger(ROOT_LOGGER).setLevel(log_level.upper())
    if db_log_level and _db_handler is not None:
        _db_handler.setLevel(db_log_level.upper())


def get_logger(component: str) -> logging.Logger:
    return logging.getLogger(f"{ROOT_LOGGER}.{component}")
