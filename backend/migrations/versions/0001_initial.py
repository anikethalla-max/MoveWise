"""Initial workspace, profile, housing and budget tables."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('workspaces',sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_table('profiles',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('workspace_id',sa.String(36),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('destination_city',sa.String(120),nullable=False),
        sa.Column('workplace_area',sa.String(120)),sa.Column('moving_date',sa.Date()),
        sa.Column('monthly_limit',sa.Numeric(12,2)),sa.Column('upfront_limit',sa.Numeric(12,2)),
        sa.Column('household_size',sa.Integer(),nullable=False),
        sa.Column('housing_preferences',sa.Text()),sa.Column('commute_preferences',sa.Text()))
    op.create_index('ix_profiles_workspace_id','profiles',['workspace_id'],unique=True)
    op.create_table('housing',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('workspace_id',sa.String(36),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('name',sa.String(120),nullable=False),sa.Column('locality',sa.String(120),nullable=False),
        sa.Column('rent',sa.Numeric(12,2)),sa.Column('maintenance',sa.Numeric(12,2)),
        sa.Column('deposit',sa.Numeric(12,2)),sa.Column('furnishing',sa.String(80)),
        sa.Column('notes',sa.Text()),sa.Column('commute_minutes',sa.Integer()),
        sa.Column('listing_link',sa.Text()),sa.Column('source',sa.String(30),nullable=False))
    op.create_index('ix_housing_workspace_id','housing',['workspace_id'])
    op.create_table('budgets',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('workspace_id',sa.String(36),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('rent',sa.Numeric(12,2)),sa.Column('maintenance',sa.Numeric(12,2)),
        sa.Column('utilities',sa.Numeric(12,2)),sa.Column('food',sa.Numeric(12,2)),
        sa.Column('transport',sa.Numeric(12,2)),sa.Column('miscellaneous',sa.Numeric(12,2)),
        sa.Column('deposit',sa.Numeric(12,2)),sa.Column('moving_costs',sa.Numeric(12,2)),
        sa.Column('setup_costs',sa.Numeric(12,2)),
        sa.UniqueConstraint('workspace_id',name='uq_budget_workspace'))
    op.create_index('ix_budgets_workspace_id','budgets',['workspace_id'])


def downgrade():
    for table in ('budgets','housing','profiles'):
        op.drop_index(f'ix_{table}_workspace_id',table_name=table)
        op.drop_table(table)
    op.drop_table('workspaces')
