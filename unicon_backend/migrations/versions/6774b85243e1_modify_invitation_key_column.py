"""Modify invitation key column

Revision ID: 6774b85243e1
Revises: 15a79027d041
Create Date: 2024-12-01 20:28:10.136191

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6774b85243e1"
down_revision: str | None = "15a79027d041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "invitationkey",
        "key",
        existing_type=sa.VARCHAR(),
        type_=sa.Uuid(),
        existing_nullable=False,
        postgresql_using="key::uuid",
    )
    op.create_unique_constraint("invitation_key_unique", "invitationkey", ["key"])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint("invitation_key_unique", "invitationkey", type_="unique")
    op.alter_column(
        "invitationkey", "key", existing_type=sa.Uuid(), type_=sa.VARCHAR(), existing_nullable=False
    )
    # ### end Alembic commands ###
