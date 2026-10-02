"""Selected homes and versioned plans with proposals."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("selected_homes",
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("housing_id", sa.String(36), sa.ForeignKey("housing.id"), nullable=False))
    op.create_table("plan_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("tasks", sa.JSON(), nullable=False),
        sa.Column("budget_concerns", sa.JSON(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("missing_information", sa.JSON(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "version", name="uq_plan_version"))
    op.create_index("ix_plan_versions_workspace_id", "plan_versions", ["workspace_id"])
    op.create_table("plan_proposals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("base_version", sa.Integer(), nullable=False),
        sa.Column("context_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("candidate", sa.JSON(), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column("applied_version", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_plan_proposals_workspace_id", "plan_proposals", ["workspace_id"])
    op.create_table("task_completions",
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("task_id", sa.String(36), primary_key=True),
        sa.Column("completed", sa.Boolean(), nullable=False))


def downgrade():
    op.drop_table("task_completions")
    op.drop_index("ix_plan_proposals_workspace_id", table_name="plan_proposals")
    op.drop_table("plan_proposals")
    op.drop_index("ix_plan_versions_workspace_id", table_name="plan_versions")
    op.drop_table("plan_versions")
    op.drop_table("selected_homes")
