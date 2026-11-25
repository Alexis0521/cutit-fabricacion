import sqlalchemy as sa
from alembic import op

revision = "20261125_order_specs_sequence"
down_revision = "20261125_update_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("fabricaciones"):
        columns = {
            column["name"] for column in inspector.get_columns("fabricaciones")
        }
        if "especificaciones" not in columns:
            op.add_column(
                "fabricaciones",
                sa.Column(
                    "especificaciones",
                    sa.JSON(),
                    nullable=False,
                    server_default=sa.text("'{}'"),
                ),
            )

    if not inspector.has_table("fabricaciones_secuencia"):
        op.create_table(
            "fabricaciones_secuencia",
            sa.Column("numero", sa.Integer(), autoincrement=True, nullable=False),
            sa.PrimaryKeyConstraint("numero"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("fabricaciones_secuencia"):
        op.drop_table("fabricaciones_secuencia")

    if inspector.has_table("fabricaciones"):
        columns = {
            column["name"] for column in inspector.get_columns("fabricaciones")
        }
        if "especificaciones" in columns:
            op.drop_column("fabricaciones", "especificaciones")
