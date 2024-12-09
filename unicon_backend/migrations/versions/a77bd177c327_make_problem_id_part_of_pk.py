"""Make problem id part of PK

Revision ID: a77bd177c327
Revises: d2b42a52397a
Create Date: 2024-12-07 19:18:32.371079

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a77bd177c327"
down_revision: str | None = "d2b42a52397a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint("task_attempt_task_id_fkey", "task_attempt", type_="foreignkey")

    op.drop_constraint("task_pkey", "task", type_="primary")
    op.create_primary_key("task_pkey", "task", ["id", "problem_id"])

    op.add_column("task_attempt", sa.Column("problem_id", sa.Integer(), nullable=False))
    op.create_foreign_key(None, "task_attempt", "task", ["id", "problem_id"], ["id", "problem_id"])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint("task_attempt_task_id_fkey", "task_attempt", type_="foreignkey")

    op.drop_constraint("task_pkey", "task", type_="primary")
    op.create_primary_key("task_pkey", "task", ["id"])

    op.create_foreign_key("task_attempt_task_id_fkey", "task_attempt", "task", ["task_id"], ["id"])
    op.drop_column("task_attempt", "problem_id")
    # ### end Alembic commands ###
