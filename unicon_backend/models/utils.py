import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg

_timestamp_column = lambda nullable, default: sa.Column(
    pg.TIMESTAMP(timezone=True),
    nullable=nullable,
    server_default=sa.func.now() if default else None,
)

__all__ = ["_timestamp_column"]
