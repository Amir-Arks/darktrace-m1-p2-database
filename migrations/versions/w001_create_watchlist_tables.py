"""create watchlist and watchlist_version tables

Revision ID: w001_watchlist
Revises: c3acc2cc0045
Create Date: 2026-10-24 13:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'w001_watchlist'
down_revision: Union[str, None] = 'c3acc2cc0045'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    id_type = sa.Integer().with_variant(sa.BigInteger(), 'postgresql')
    op.create_table(
        'watchlist',
        sa.Column('watchlist_id', id_type, autoincrement=True, nullable=False, comment='Watchlist identifier.'),
        sa.Column('name', sa.String(length=150), nullable=False, comment='Human-readable watchlist name.'),
        sa.Column('description', sa.Text(), nullable=True, comment='Detailed watchlist description.'),
        sa.Column('owner_id', sa.String(length=150), nullable=False, comment='Owner / team responsible for this watchlist.'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('current_version_id', id_type, nullable=True, comment='Pointer to the active version_id in watchlist_version.'),
        sa.PrimaryKeyConstraint('watchlist_id', name='pk_watchlist'),
        sa.UniqueConstraint('owner_id', 'name', name='uq_watchlist_owner_name')
    )

    op.create_table(
        'watchlist_version',
        sa.Column('version_id', id_type, autoincrement=True, nullable=False, comment='Unique identifier for this version record.'),
        sa.Column('watchlist_id', id_type, nullable=False, comment='FK → watchlist.watchlist_id.'),
        sa.Column('version_number', sa.Integer(), nullable=False, comment='Sequential version number (1, 2, 3...) per watchlist.'),
        sa.Column('expression', sa.Text(), nullable=False, comment='Matching logic / rule expression.'),
        sa.Column('scope', sa.Text(), nullable=False, comment='Scope of the watchlist.'),
        sa.Column('severity', sa.String(length=20), nullable=False, comment='Severity level: low | medium | high | critical.'),
        sa.Column('created_by', sa.String(length=150), nullable=False, comment='User / analyst who authored this version.'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')", name='ck_watchlist_version_severity'),
        sa.CheckConstraint('version_number > 0', name='ck_watchlist_version_number_positive'),
        sa.ForeignKeyConstraint(['watchlist_id'], ['watchlist.watchlist_id'], name='fk_watchlist_version_watchlist_id_watchlist', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('version_id', name='pk_watchlist_version'),
        sa.UniqueConstraint('watchlist_id', 'version_number', name='uq_watchlist_version_number'),
        sa.UniqueConstraint('watchlist_id', 'version_id', name='uq_watchlist_version_pair')
    )

    op.create_index(
        'idx_watchlist_version_history',
        'watchlist_version',
        ['watchlist_id', 'version_number'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('idx_watchlist_version_history', table_name='watchlist_version')
    op.drop_table('watchlist_version')
    op.drop_table('watchlist')
