"""Production entry point: ``python -m app``.

Runs uvicorn in-process (one Python process, no reloader, no Node.js) and
keeps a handle to the server so ``POST /api/system/shutdown`` and Ctrl+C both
shut down gracefully.
"""
from __future__ import annotations

import uvicorn

from app.config import get_settings
from app.main import create_app


def main() -> None:
    cfg = get_settings()
    app = create_app(cfg)
    # log_config=None: keep our JSON/DB logging; uvicorn's dictConfig would close our handlers.
    config = uvicorn.Config(app, host=cfg.host, port=cfg.port, log_config=None, access_log=False,
                            lifespan="on", ws_ping_interval=20, timeout_graceful_shutdown=5)
    server = uvicorn.Server(config)
    app.state.lab.server = server
    server.run()


if __name__ == "__main__":
    main()
