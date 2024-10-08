"""Add definition and task table

Revision ID: 34d40a4b8879
Revises: a3e28e9d0b43
Create Date: 2024-10-01 02:44:53.899053

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "34d40a4b8879"
down_revision: str | None = "a3e28e9d0b43"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

task_type_enum = sa.Enum(
    "MULTIPLE_CHOICE", "MULTIPLE_RESPONSE", "SHORT_ANSWER", "PROGRAMMING", name="task_type"
)


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "definition",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "task",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", task_type_enum, nullable=False),
        sa.Column("autograde", sa.Boolean(), nullable=False),
        sa.Column("other_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("definition_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["definition_id"], ["definition.id"]),
        sa.PrimaryKeyConstraint("id", "definition_id"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("task")
    op.drop_table("definition")

    task_type_enum.drop(op.get_bind())
    # ### end Alembic commands ###
