"""Store optional auxiliary outputs from the fine-tuned affect model."""
from alembic import op
from sqlalchemy import Column, Float, inspect
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column['name'] for column in inspect(op.get_bind()).get_columns('attentiveness_readings')}
    for name in ('boredom', 'confusion'):
        if name not in columns:
            op.add_column('attentiveness_readings', Column(name, Float(), nullable=True))


def downgrade():
    with op.batch_alter_table('attentiveness_readings') as batch:
        batch.drop_column('boredom')
        batch.drop_column('confusion')
