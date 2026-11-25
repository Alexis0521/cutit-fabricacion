import sqlalchemy as sa
from alembic import op

revision = "20261125_fabricante_id"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("fabricaciones"):
        return

    columns = {column["name"] for column in inspector.get_columns("fabricaciones")}
    if "fabricante_id" not in columns:
        op.add_column(
            "fabricaciones",
            sa.Column("fabricante_id", sa.String(length=100), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("fabricaciones"):
        return

    columns = {column["name"] for column in inspector.get_columns("fabricaciones")}
    if "fabricante_id" in columns:
        op.drop_column("fabricaciones", "fabricante_id")
