"""검토·승인 거버넌스 1단계 — 이력·재오픈 요청·외부 승인 + 스코핑 결재 칸 (ADR-0038)

Revision ID: 9b2c4d6e8f10
Revises: 6b6d7fd94f0d
Create Date: 2026-10-03 00:00:00.000000+00:00

**추가만 한다 — 기존 데이터를 바꾸지 않는다.** 새 테이블 4개(`governance_events`·`reopen_requests`·
`external_approvals`·`governance_files`)와 `scopings` 결재 칸 6개(전부 NULL 허용, `version` 은 기본 1).
`governance_events` 는 **append-only** — PostgreSQL 트리거가 UPDATE·DELETE 를 거부한다(앱 버그로도 이력을 못 지운다).
새 역할 코드(`icfr_staff`·`icfr_lead`)는 문자열 컬럼 값이라 스키마 변경이 없다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = '9b2c4d6e8f10'
down_revision: Union[str, None] = '6b6d7fd94f0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _audit_cols() -> list:
    return [
        sa.Column('id', PG_UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('tenant_id', PG_UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_by', sa.String(255), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.String(255), nullable=True),
        sa.Column('row_version', sa.Integer(), server_default='1', nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        'governance_events', *_audit_cols(),
        sa.Column('entity_type', sa.String(30), nullable=False),
        sa.Column('entity_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(30), nullable=False),
        sa.Column('target', sa.String(300), nullable=True),
        sa.Column('actor_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('before', sa.JSON(), nullable=True),
        sa.Column('after', sa.JSON(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=True),
    )
    op.create_index('ix_governance_events_entity_id', 'governance_events', ['entity_id'])
    op.create_index('ix_governance_events_entity_created', 'governance_events', ['entity_type', 'entity_id', 'created_at'])
    op.create_table(
        'reopen_requests', *_audit_cols(),
        sa.Column('entity_type', sa.String(30), nullable=False),
        sa.Column('entity_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('requested_by_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('requested_tier', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('decided_by_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decision_reason', sa.Text(), nullable=True),
    )
    op.create_index('ix_reopen_requests_entity_id', 'reopen_requests', ['entity_id'])
    op.create_table(
        'external_approvals', *_audit_cols(),
        sa.Column('entity_type', sa.String(30), nullable=False),
        sa.Column('entity_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('purpose', sa.String(20), nullable=False),
        sa.Column('reopen_request_id', PG_UUID(as_uuid=True), sa.ForeignKey('reopen_requests.id'), nullable=True),
        sa.Column('approver_body', sa.String(20), nullable=False),
        sa.Column('approved_on', sa.Date(), nullable=False),
        sa.Column('reference', sa.String(300), nullable=True),
        sa.Column('recorded_by_id', PG_UUID(as_uuid=True), nullable=False),
    )
    op.create_index('ix_external_approvals_entity_id', 'external_approvals', ['entity_id'])
    op.create_table(
        'governance_files', *_audit_cols(),
        sa.Column('external_approval_id', PG_UUID(as_uuid=True), sa.ForeignKey('external_approvals.id'), nullable=False),
        sa.Column('filename', sa.String(300), nullable=False),
        sa.Column('mime_type', sa.String(120), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('minio_key', sa.String(500), nullable=False),
    )
    op.create_index('ix_governance_files_external_approval_id', 'governance_files', ['external_approval_id'])

    for name, col in [('review_requested_by_id', PG_UUID(as_uuid=True)),
                      ('review_requested_at', sa.DateTime(timezone=True)),
                      ('review_path', sa.String(20)),
                      ('reviewed_by_id', PG_UUID(as_uuid=True)),
                      ('reviewed_at', sa.DateTime(timezone=True))]:
        op.add_column('scopings', sa.Column(name, col, nullable=True))
    op.add_column('scopings', sa.Column('version', sa.Integer(), server_default='1', nullable=False))

    # append-only — 이력은 고칠 수도 지울 수도 없다
    op.execute("""
        CREATE OR REPLACE FUNCTION governance_events_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'governance_events 는 추가만 가능합니다 (ADR-0038 §2.4) — % 거부', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_governance_events_append_only
        BEFORE UPDATE OR DELETE ON governance_events
        FOR EACH ROW EXECUTE FUNCTION governance_events_append_only();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_governance_events_append_only ON governance_events")
    op.execute("DROP FUNCTION IF EXISTS governance_events_append_only()")
    for name in ('version', 'reviewed_at', 'reviewed_by_id', 'review_path', 'review_requested_at',
                 'review_requested_by_id'):
        op.drop_column('scopings', name)
    op.drop_index('ix_governance_files_external_approval_id', table_name='governance_files')
    op.drop_table('governance_files')
    op.drop_index('ix_external_approvals_entity_id', table_name='external_approvals')
    op.drop_table('external_approvals')
    op.drop_index('ix_reopen_requests_entity_id', table_name='reopen_requests')
    op.drop_table('reopen_requests')
    op.drop_index('ix_governance_events_entity_created', table_name='governance_events')
    op.drop_index('ix_governance_events_entity_id', table_name='governance_events')
    op.drop_table('governance_events')
