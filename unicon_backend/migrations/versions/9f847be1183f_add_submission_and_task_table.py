"""Add submission and task table

Revision ID: 9f847be1183f
Revises: 34d40a4b8879
Create Date: 2024-10-01 10:08:59.704231

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "9f847be1183f"
down_revision: str | None = "34d40a4b8879"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

submission_status_enum = sa.Enum("Pending", "Ok", name="submissionstatus")
task_result_status_enum = sa.Enum("SUCCESS", "PENDING", "SKIPPED", "FAILED", name="taskevalstatus")


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "submission",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("status", submission_status_enum, nullable=False),
        sa.Column("definition_id", sa.Integer(), nullable=True),
        sa.Column(
            "submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("other_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["definition_id"], ["definition.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "task_result",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("definition_id", sa.Integer(), nullable=True),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("job_id", sa.String(), nullable=True),
        sa.Column("status", task_result_status_enum, nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["submission_id"], ["submission.id"]),
        sa.ForeignKeyConstraint(["definition_id", "task_id"], ["task.definition_id", "task.id"]),
        sa.UniqueConstraint("job_id"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("task_result")
    op.drop_table("submission")

    submission_status_enum.drop(op.get_bind())
    task_result_status_enum.drop(op.get_bind())
    # ### end Alembic commands ###
