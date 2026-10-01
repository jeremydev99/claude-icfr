"""스코핑 계정 → 재무제표 계정 참조 (8-E, ADR-0037 §6)

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-09-30 01:00:00.000000+00:00

**컬럼 1개를 추가할 뿐 기존 데이터를 바꾸지 않는다.** `scoping_accounts.fs_account_id` 는 nullable —
기존 행(2026 스코핑 등 템플릿 복사)은 NULL 로 남는다(마스터 확정 A안: 2026 은 그대로, 다음 회계연도부터
재무제표 기반). 같은 테넌트 계정만 가리키도록 `(fs_account_id, tenant_id)` 복합 FK(ADR-0030 §2.3).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = 'f5a6b7c8d9e0'
down_revision: Union[str, None] = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('scoping_accounts', sa.Column('fs_account_id', PG_UUID(as_uuid=True), nullable=True))
    op.create_index('ix_scoping_accounts_fs_account_id', 'scoping_accounts', ['fs_account_id'])
    op.create_foreign_key('fk_scoping_accounts_fs_account_tenant', 'scoping_accounts', 'fs_accounts',
                          ['fs_account_id', 'tenant_id'], ['id', 'tenant_id'])


def downgrade() -> None:
    op.drop_constraint('fk_scoping_accounts_fs_account_tenant', 'scoping_accounts', type_='foreignkey')
    op.drop_index('ix_scoping_accounts_fs_account_id', table_name='scoping_accounts')
    op.drop_column('scoping_accounts', 'fs_account_id')
