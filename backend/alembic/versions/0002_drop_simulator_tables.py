"""Drop simulator/bot tables (Phase 1 of the monitoring platform redesign).

Keeps ``system_logs`` and ``app_settings``. The old simulator data is not
migrated (decision recorded in PROJECT_AUDIT.md); the application writes a
backup of the database file before this migration runs.

Revision ID: 0002
Revises: 0001
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Dependants first so foreign keys never block the drop.
SIMULATOR_TABLES = ("stat_snapshots", "match_events", "player_statistics", "match_participants",
                    "match_sessions", "players")


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    for name in SIMULATOR_TABLES:
        if name in existing:
            op.drop_table(name)


def downgrade() -> None:
    raise NotImplementedError(
        "Simulator tables are not recreated. Restore the backup from backend/data/backups "
        "or check out the archive/v1-simulator branch."
    )
