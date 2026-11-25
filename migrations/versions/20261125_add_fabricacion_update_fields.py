import sqlalchemy as sa
from alembic import op

revision = "20261125_update_fields"
down_revision = "20261125_fabricante_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("fabricaciones"):
        return

    columns = {column["name"] for column in inspector.get_columns("fabricaciones")}
    if "especificaciones_tecnicas" not in columns:
        op.add_column(
            "fabricaciones",
            sa.Column("especificaciones_tecnicas", sa.Text(), nullable=True),
        )
    if "insumos_terceros" not in columns:
        op.add_column(
            "fabricaciones",
            sa.Column("insumos_terceros", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("fabricaciones"):
        return

    columns = {column["name"] for column in inspector.get_columns("fabricaciones")}
    if "insumos_terceros" in columns:
        op.drop_column("fabricaciones", "insumos_terceros")
    if "especificaciones_tecnicas" in columns:
        op.drop_column("fabricaciones", "especificaciones_tecnicas")
