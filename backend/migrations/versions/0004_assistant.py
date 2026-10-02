"""Workspace conversations, bounded runs and observable events."""
from alembic import op
import sqlalchemy as sa

revision='0004'
down_revision='0003'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('conversations',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('workspace_id',sa.String(36),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('title',sa.String(160),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_conversations_workspace_id','conversations',['workspace_id'])
    op.create_table('agent_runs',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('conversation_id',sa.String(36),sa.ForeignKey('conversations.id'),nullable=False),
        sa.Column('workspace_id',sa.String(36),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('parent_run_id',sa.String(36),sa.ForeignKey('agent_runs.id')),
        sa.Column('request_key',sa.String(80)),
        sa.Column('agent',sa.String(30),nullable=False),sa.Column('status',sa.String(20),nullable=False),
        sa.Column('request',sa.Text(),nullable=False),sa.Column('result',sa.JSON()),sa.Column('error',sa.Text()),
        sa.Column('cancel_requested',sa.Boolean(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('workspace_id','request_key',name='uq_run_request_key'))
    op.create_index('ix_agent_runs_conversation_id','agent_runs',['conversation_id'])
    op.create_index('ix_agent_runs_workspace_id','agent_runs',['workspace_id'])
    op.create_index('ix_agent_runs_parent_run_id','agent_runs',['parent_run_id'])
    op.create_table('assistant_messages',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('conversation_id',sa.String(36),sa.ForeignKey('conversations.id'),nullable=False),
        sa.Column('workspace_id',sa.String(36),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('run_id',sa.String(36),sa.ForeignKey('agent_runs.id')),
        sa.Column('role',sa.String(20),nullable=False),sa.Column('content',sa.Text(),nullable=False),
        sa.Column('payload',sa.JSON()),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_assistant_messages_conversation_id','assistant_messages',['conversation_id'])
    op.create_index('ix_assistant_messages_workspace_id','assistant_messages',['workspace_id'])
    op.create_table('run_events',
        sa.Column('id',sa.Integer(),primary_key=True,autoincrement=True),
        sa.Column('root_run_id',sa.String(36),sa.ForeignKey('agent_runs.id'),nullable=False),
        sa.Column('agent_run_id',sa.String(36),sa.ForeignKey('agent_runs.id'),nullable=False),
        sa.Column('workspace_id',sa.String(36),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('event_type',sa.String(30),nullable=False),sa.Column('agent',sa.String(30),nullable=False),
        sa.Column('tool_name',sa.String(80)),sa.Column('status',sa.String(20),nullable=False),
        sa.Column('summary',sa.String(300),nullable=False),sa.Column('details',sa.JSON()),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_run_events_root_run_id','run_events',['root_run_id'])
    op.create_index('ix_run_events_agent_run_id','run_events',['agent_run_id'])
    op.create_index('ix_run_events_workspace_id','run_events',['workspace_id'])


def downgrade():
    for table,indexes in [('run_events',['root_run_id','agent_run_id','workspace_id']),
                          ('assistant_messages',['conversation_id','workspace_id']),
                          ('agent_runs',['conversation_id','workspace_id','parent_run_id']),
                          ('conversations',['workspace_id'])]:
        for name in indexes:op.drop_index(f'ix_{table}_{name}',table_name=table)
        op.drop_table(table)
