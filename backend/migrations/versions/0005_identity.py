"""Map verified OIDC identities to workspaces."""
from alembic import op
import sqlalchemy as sa

revision='0005'
down_revision='0004'
branch_labels=None
depends_on=None


def upgrade():
    with op.batch_alter_table('workspaces') as batch:
        batch.add_column(sa.Column('identity_issuer',sa.String(255)))
        batch.add_column(sa.Column('identity_subject',sa.String(255)))
        batch.create_unique_constraint('uq_workspace_identity',['identity_issuer','identity_subject'])


def downgrade():
    with op.batch_alter_table('workspaces') as batch:
        batch.drop_constraint('uq_workspace_identity',type_='unique')
        batch.drop_column('identity_subject')
        batch.drop_column('identity_issuer')
