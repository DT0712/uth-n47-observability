"""su co thu nghiem: incidents.fault_run_id, loai su kien fault_run (BR-09)

Revision ID: 7c1e2a9b4d30
Revises: e654f1dadb50
Create Date: 2026-11-26 19:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7c1e2a9b4d30'
down_revision: Union[str, None] = 'e654f1dadb50'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_TYPES = ('opened', 'episode_firing', 'episode_resolved', 'acknowledged', 'note', 'false_positive', 'closed')
NEW_TYPES = OLD_TYPES + ('fault_run',)


def _in(values: tuple[str, ...]) -> str:
    return f"type IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    # batch: SQLite không ALTER được FK/CHECK, Alembic dựng lại bảng; PostgreSQL chạy ALTER thường
    with op.batch_alter_table('incidents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('fault_run_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_incidents_fault_run_id'), ['fault_run_id'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_incidents_fault_run_id_fault_runs'), 'fault_runs',
                                    ['fault_run_id'], ['id'])
    with op.batch_alter_table('incident_events', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('ck_incident_events_type'), type_='check')
        batch_op.create_check_constraint('type', _in(NEW_TYPES))


def downgrade() -> None:
    op.execute("DELETE FROM incident_events WHERE type = 'fault_run'")
    with op.batch_alter_table('incident_events', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('ck_incident_events_type'), type_='check')
        batch_op.create_check_constraint('type', _in(OLD_TYPES))
    with op.batch_alter_table('incidents', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_incidents_fault_run_id_fault_runs'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_incidents_fault_run_id'))
        batch_op.drop_column('fault_run_id')
