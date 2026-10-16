"""initial workspace schema
Revision ID: e6ae75c83725
Revises: 
"""
from alembic import op
import sqlalchemy as sa

revision = 'e6ae75c83725'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('eval_results',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('provider', sa.String(length=40), nullable=False),
    sa.Column('result', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('profile', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('solicitations',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('owner_id', sa.String(length=64), nullable=False),
    sa.Column('title', sa.String(length=250), nullable=False),
    sa.Column('filename', sa.String(length=250), nullable=False),
    sa.Column('source_url', sa.Text(), nullable=True),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('pages', sa.JSON(), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('analysis', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_solicitations_content_hash'), 'solicitations', ['content_hash'], unique=False)
    op.create_index(op.f('ix_solicitations_created_at'), 'solicitations', ['created_at'], unique=False)
    op.create_index(op.f('ix_solicitations_owner_id'), 'solicitations', ['owner_id'], unique=False)
    if op.get_bind().dialect.name == 'postgresql':
        op.execute("CREATE INDEX ix_solicitations_fts ON solicitations USING gin(to_tsvector('english', content))")
    op.create_table('briefs',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('solicitation_id', sa.String(length=36), nullable=False),
    sa.Column('version', sa.String(length=64), nullable=False),
    sa.Column('content', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['solicitation_id'], ['solicitations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_briefs_solicitation_id'), 'briefs', ['solicitation_id'], unique=False)
    op.create_table('processing_jobs',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('solicitation_id', sa.String(length=36), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('available_at', sa.DateTime(), nullable=False),
    sa.Column('claimed_at', sa.DateTime(), nullable=True),
    sa.Column('lease_token', sa.String(length=36), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['solicitation_id'], ['solicitations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_jobs_ready', 'processing_jobs', ['status', 'available_at'], unique=False)
    op.create_index(op.f('ix_processing_jobs_solicitation_id'), 'processing_jobs', ['solicitation_id'], unique=False)
    op.create_table('requirements',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('solicitation_id', sa.String(length=36), nullable=False),
    sa.Column('category', sa.String(length=32), nullable=False),
    sa.Column('claim', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['solicitation_id'], ['solicitations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_requirements_category'), 'requirements', ['category'], unique=False)
    op.create_index(op.f('ix_requirements_solicitation_id'), 'requirements', ['solicitation_id'], unique=False)
    op.create_table('review_decisions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('solicitation_id', sa.String(length=36), nullable=False),
    sa.Column('owner_id', sa.String(length=64), nullable=False),
    sa.Column('brief_version', sa.String(length=64), nullable=False),
    sa.Column('decision', sa.String(length=20), nullable=False),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.Column('reviewed_fact_ids', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['solicitation_id'], ['solicitations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_review_decisions_solicitation_id'), 'review_decisions', ['solicitation_id'], unique=False)

def downgrade():
    op.drop_index(op.f('ix_review_decisions_solicitation_id'), table_name='review_decisions')
    op.drop_table('review_decisions')
    op.drop_index(op.f('ix_requirements_solicitation_id'), table_name='requirements')
    op.drop_index(op.f('ix_requirements_category'), table_name='requirements')
    op.drop_table('requirements')
    op.drop_index(op.f('ix_processing_jobs_solicitation_id'), table_name='processing_jobs')
    op.drop_index('ix_jobs_ready', table_name='processing_jobs')
    op.drop_table('processing_jobs')
    op.drop_index(op.f('ix_briefs_solicitation_id'), table_name='briefs')
    op.drop_table('briefs')
    if op.get_bind().dialect.name == 'postgresql':
        op.drop_index('ix_solicitations_fts', table_name='solicitations')
    op.drop_index(op.f('ix_solicitations_owner_id'), table_name='solicitations')
    op.drop_index(op.f('ix_solicitations_created_at'), table_name='solicitations')
    op.drop_index(op.f('ix_solicitations_content_hash'), table_name='solicitations')
    op.drop_table('solicitations')
    op.drop_table('users')
    op.drop_table('eval_results')
