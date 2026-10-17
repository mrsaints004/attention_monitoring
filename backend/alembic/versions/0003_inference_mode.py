"""Distinguish geometric estimates from readings with an affect model."""
from alembic import op
from sqlalchemy import Column, String, inspect
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    if 'inference_mode' not in {c['name'] for c in inspect(op.get_bind()).get_columns('attentiveness_readings')}:
        op.add_column('attentiveness_readings', Column('inference_mode', String(16), nullable=False, server_default='geometric'))


def downgrade():
    with op.batch_alter_table('attentiveness_readings') as batch:
        batch.drop_column('inference_mode')
