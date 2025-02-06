"""initialize groups

Revision ID: 04de0314e0a9
Revises: 7861878b3343
Create Date: 2025-02-06 21:56:29.653264

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "04de0314e0a9"
down_revision: str | None = "7861878b3343"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "group",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name=op.f("fk_group_project_id_project")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_group")),
    )
    op.create_table(
        "group_member",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("is_supervisor", sa.Boolean(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(
            ["group_id"], ["group.id"], name=op.f("fk_group_member_group_id_group")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name=op.f("fk_group_member_user_id_user")
        ),
        sa.PrimaryKeyConstraint("user_id", "group_id", name=op.f("pk_group_member")),
    )
    op.add_column(
        "role",
        sa.Column(
            "view_supervised_submission_access", sa.Boolean(), server_default="0", nullable=False
        ),
    )
    op.add_column(
        "role", sa.Column("view_groups_access", sa.Boolean(), server_default="0", nullable=False)
    )
    op.add_column(
        "role", sa.Column("create_groups_access", sa.Boolean(), server_default="0", nullable=False)
    )
    op.add_column(
        "role", sa.Column("edit_groups_access", sa.Boolean(), server_default="0", nullable=False)
    )
    op.add_column(
        "role", sa.Column("delete_groups_access", sa.Boolean(), server_default="0", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("role", "view_supervised_submission_access")
    op.drop_column("role", "delete_groups_access")
    op.drop_column("role", "edit_groups_access")
    op.drop_column("role", "create_groups_access")
    op.drop_column("role", "view_groups_access")
    op.drop_table("group_member")
    op.drop_table("group")
