"""Create schema or preserve existing readings while allowing unknown indices."""
from alembic import op
from sqlalchemy import inspect, Float
from app.database import Base
import app.models  # noqa
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if not inspect(connection).has_table("attentiveness_readings"):
        Base.metadata.create_all(connection)
    elif not next(c for c in inspect(connection).get_columns("attentiveness_readings") if c["name"] == "attention_index")["nullable"]:
        with op.batch_alter_table("attentiveness_readings") as batch:
            batch.alter_column("attention_index", existing_type=Float(), nullable=True)
    op.execute("UPDATE attentiveness_readings SET attention_index = NULL WHERE quality_flag != 'normal'")


def downgrade():
    raise RuntimeError("Downgrade would discard unknown readings; restore a backup instead.")
