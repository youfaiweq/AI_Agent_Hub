"""Approval request persistence operations."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentApproval, ApprovalStatus


class ApprovalRepository:
    """Persist one approval decision per pending tool call."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        agent_run_id: UUID,
        call_id: str,
        tool_name: str,
        arguments: dict[str, object] | None,
        expires_at: datetime,
    ) -> AgentApproval:
        approval = AgentApproval(
            agent_run_id=agent_run_id,
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments,
            status=ApprovalStatus.PENDING,
            expires_at=expires_at,
        )
        self.session.add(approval)
        await self.session.flush()
        await self.session.refresh(approval)
        return approval

    async def get_for_run(self, agent_run_id: UUID) -> AgentApproval | None:
        result = await self.session.execute(
            select(AgentApproval)
            .where(AgentApproval.agent_run_id == agent_run_id)
            .order_by(AgentApproval.created_at.desc(), AgentApproval.id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        approval: AgentApproval,
        status: ApprovalStatus,
    ) -> AgentApproval:
        approval.status = status
        approval.decided_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(approval)
        return approval
