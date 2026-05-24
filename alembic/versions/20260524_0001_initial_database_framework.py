"""Create the initial database framework tables."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260524_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the first set of persistent application tables."""
    op.create_table(
        "persisted_config_items",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_persisted_config_items")),
    )
    op.create_table(
        "query_records",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("query", sa.String(length=512), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("source_tool", sa.String(length=128), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_query_records")),
    )
    op.create_index(
        op.f("ix_query_records_created_at"),
        "query_records",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_query_records_provider"),
        "query_records",
        ["provider"],
        unique=False,
    )
    op.create_table(
        "task_execution_records",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("task_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_execution_records")),
    )
    op.create_index(
        op.f("ix_task_execution_records_created_at"),
        "task_execution_records",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_task_execution_records_task_name"),
        "task_execution_records",
        ["task_name"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the initial persistence tables in reverse dependency order."""
    op.drop_index(
        op.f("ix_task_execution_records_task_name"),
        table_name="task_execution_records",
    )
    op.drop_index(
        op.f("ix_task_execution_records_created_at"),
        table_name="task_execution_records",
    )
    op.drop_table("task_execution_records")
    op.drop_index(op.f("ix_query_records_provider"), table_name="query_records")
    op.drop_index(op.f("ix_query_records_created_at"), table_name="query_records")
    op.drop_table("query_records")
    op.drop_table("persisted_config_items")
