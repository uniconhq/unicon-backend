"""initialize permissions

Revision ID: 7861878b3343
Revises: 54e4afebdfe4
Create Date: 2025-02-02 21:32:15.105055

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7861878b3343"
down_revision: str | None = "54e4afebdfe4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = [
    "view_problems_access",
    "view_full_problem_details_access",
    "create_problems_access",
    "edit_problems_access",
    "delete_problems_access",
    "view_restricted_problems_access",
    "view_full_restricted_problem_details_access",
    "edit_restricted_problems_access",
    "delete_restricted_problems_access",
    "make_submission_access",
    "view_own_submission_access",
    "view_others_submission_access",
]


def upgrade() -> None:
    for permission in PERMISSIONS:
        op.add_column(
            "role",
            sa.Column(permission, sa.Boolean(), server_default="0", nullable=False),
        )


def downgrade() -> None:
    for permission in PERMISSIONS:
        op.drop_column("role", permission)
