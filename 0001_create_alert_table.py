"""create alert table

Revision ID: 0001_alert
Revises: 0000_stub   (change to the real latest revision when merging)
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_alert"
down_revision = "0000_stub"
branch_labels = None
depends_on = None

SEVERITIES = ("low", "medium", "high", "critical")
STATES = ("new", "acknowledged", "investigating", "escalated", "resolved", "false_positive")


def upgrade() -> None:
    op.create_table(
        "alert",
        sa.Column("alert_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("source_id", sa.Integer, nullable=False),
        sa.Column("doc_id", sa.String(64), nullable=True),
        sa.Column("watchlist_id", sa.Integer, nullable=True),
        sa.Column("severity",
                  sa.Enum(*SEVERITIES, name="alert_severity", native_enum=False,
                          length=20, create_constraint=True),
                  nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("threat_score", sa.Integer, nullable=False),
        sa.Column("explain_ref", sa.String(255), nullable=True),
        sa.Column("state",
                  sa.Enum(*STATES, name="alert_state", native_enum=False,
                          length=20, create_constraint=True),
                  nullable=False, server_default="new"),
        sa.Column("assigned_to", sa.String(100), nullable=True),
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer, nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["source_id"], ["source.source_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["watchlist_id"], ["watchlist.watchlist_id"], ondelete="SET NULL"),
        sa.UniqueConstraint("fingerprint", name="uq_alert_fingerprint"),
        sa.CheckConstraint("threat_score >= 0 AND threat_score <= 100", name="ck_alert_threat_score_range"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_alert_confidence_range"),
        sa.CheckConstraint("count >= 1", name="ck_alert_count_positive"),
        sa.CheckConstraint("last_seen >= first_seen", name="ck_alert_seen_order"),
    )
    op.create_index("ix_alert_state", "alert", ["state"])
    op.create_index("ix_alert_severity", "alert", ["severity"])
    op.create_index("ix_alert_source_id", "alert", ["source_id"])
    op.create_index("ix_alert_watchlist_id", "alert", ["watchlist_id"])
    op.create_index("ix_alert_state_severity", "alert", ["state", "severity"])
    op.create_index("ix_alert_last_seen", "alert", ["last_seen"])


def downgrade() -> None:
    for name in ("ix_alert_last_seen", "ix_alert_state_severity", "ix_alert_watchlist_id",
                 "ix_alert_source_id", "ix_alert_severity", "ix_alert_state"):
        op.drop_index(name, table_name="alert")
    op.drop_table("alert")
