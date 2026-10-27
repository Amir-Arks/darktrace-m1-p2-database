"""create alert table

Revision ID: a001_alert
Revises: w001_watchlist
Create Date: 2026-10-24 13:51:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a001_alert'
down_revision: Union[str, None] = 'w001_watchlist'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEVERITIES = ('low', 'medium', 'high', 'critical')
STATES = ('new', 'acknowledged', 'investigating', 'escalated', 'resolved', 'false_positive')


def upgrade() -> None:
    op.create_table(
        'alert',
        sa.Column('alert_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('fingerprint', sa.String(length=64), nullable=False),
        sa.Column('source_id', sa.Uuid(), nullable=False),
        sa.Column('doc_id', sa.String(length=64), nullable=True),
        sa.Column('watchlist_id', sa.BigInteger(), nullable=True),
        sa.Column('severity', sa.Enum(*SEVERITIES, name='alert_severity', native_enum=False, length=20, create_constraint=True), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('threat_score', sa.Integer(), nullable=False),
        sa.Column('explain_ref', sa.String(length=255), nullable=True),
        sa.Column('state', sa.Enum(*STATES, name='alert_state', native_enum=False, length=20, create_constraint=True), server_default='new', nullable=False),
        sa.Column('assigned_to', sa.String(length=100), nullable=True),
        sa.Column('escalated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('count', sa.Integer(), server_default='1', nullable=False),
        sa.CheckConstraint('confidence >= 0 AND confidence <= 1', name='ck_alert_confidence_range'),
        sa.CheckConstraint('count >= 1', name='ck_alert_count_positive'),
        sa.CheckConstraint('last_seen >= first_seen', name='ck_alert_seen_order'),
        sa.CheckConstraint('threat_score >= 0 AND threat_score <= 100', name='ck_alert_threat_score_range'),
        sa.ForeignKeyConstraint(['source_id'], ['source.source_id'], name='fk_alert_source_id_source', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['watchlist_id'], ['watchlist.watchlist_id'], name='fk_alert_watchlist_id_watchlist', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('alert_id', name='pk_alert'),
        sa.UniqueConstraint('fingerprint', name='uq_alert_fingerprint')
    )
    op.create_index('ix_alert_last_seen', 'alert', ['last_seen'], unique=False)
    op.create_index('ix_alert_severity', 'alert', ['severity'], unique=False)
    op.create_index('ix_alert_source_id', 'alert', ['source_id'], unique=False)
    op.create_index('ix_alert_state', 'alert', ['state'], unique=False)
    op.create_index('ix_alert_state_severity', 'alert', ['state', 'severity'], unique=False)
    op.create_index('ix_alert_watchlist_id', 'alert', ['watchlist_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_alert_watchlist_id', table_name='alert')
    op.drop_index('ix_alert_state_severity', table_name='alert')
    op.drop_index('ix_alert_state', table_name='alert')
    op.drop_index('ix_alert_source_id', table_name='alert')
    op.drop_index('ix_alert_severity', table_name='alert')
    op.drop_index('ix_alert_last_seen', table_name='alert')
    op.drop_table('alert')
