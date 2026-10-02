"""Allow local embedding models with their native vector dimensions."""
from alembic import op

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector USING embedding::vector')


def downgrade():
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)')
