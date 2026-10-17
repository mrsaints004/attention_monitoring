"""Record explicit consent separately from student identity."""
from alembic import op
from sqlalchemy import Column, String, DateTime, inspect
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    columns = {c['name'] for c in inspect(op.get_bind()).get_columns('students')}
    if 'consent_version' not in columns:
        op.add_column('students', Column('consent_version', String(16), nullable=True))
    if 'consented_at' not in columns:
        op.add_column('students', Column('consented_at', DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('students') as batch:
        batch.drop_column('consent_version')
        batch.drop_column('consented_at')
