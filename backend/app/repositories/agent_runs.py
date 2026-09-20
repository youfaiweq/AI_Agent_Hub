"""Persistence operations for agent runs and tool-call records."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentRun, AgentRunStatus, ToolCallRecord, ToolCallStatus


class AgentRunRepository:
    """Create and update durable agent-run state snapshots."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        user_id: UUID,
        agent_id: UUID,
        input_text: str,
        max_steps: int,
        timeout_seconds: float,
        conversation_id: UUID | None = None,
        knowledge_base_id: UUID | None = None,
        state: dict[str, object] | None = None,
    ) -> AgentRun:
        run = AgentRun(
            user_id=user_id,
            agent_id=agent_id,
            conversation_id=conversation_id,
            knowledge_base_id=knowledge_base_id,
            input_text=input_text,
            status=AgentRunStatus.PENDING,
            max_steps=max_steps,
            timeout_seconds=timeout_seconds,
            state=state,
        )
        self.session.add(run)
        await self.session.flush()
        await self.session.refresh(run)
        return run

    async def get_owned(self, run_id: UUID, user_id: UUID) -> AgentRun | None:
        result = await self.session.execute(
            select(AgentRun).where(AgentRun.id == run_id, AgentRun.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_for_agent(self, agent_id: UUID, user_id: UUID) -> list[AgentRun]:
        result = await self.session.execute(
            select(AgentRun)
            .where(AgentRun.agent_id == agent_id, AgentRun.user_id == user_id)
            .order_by(AgentRun.created_at.desc(), AgentRun.id)
        )
        return list(result.scalars().all())

    async def update_state(
        self,
        run: AgentRun,
        *,
        status: AgentRunStatus,
        state: dict[str, object],
        step_count: int,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> AgentRun:
        now = datetime.now(UTC)
        run.status = status
        run.state = state
        run.step_count = step_count
        run.error_code = error_code
        run.error_message = error_message
        if status == AgentRunStatus.RUNNING and run.started_at is None:
            run.started_at = now
        if status in {
            AgentRunStatus.COMPLETED,
            AgentRunStatus.FAILED,
            AgentRunStatus.CANCELLED,
        }:
            run.finished_at = now
        await self.session.flush()
        await self.session.refresh(run)
        return run


class ToolCallRepository:
    """Create and complete durable tool-call audit records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_run(self, agent_run_id: UUID) -> list[ToolCallRecord]:
        result = await self.session.execute(
            select(ToolCallRecord)
            .where(ToolCallRecord.agent_run_id == agent_run_id)
            .order_by(ToolCallRecord.created_at, ToolCallRecord.id)
        )
        return list(result.scalars().all())

    async def get_for_run_call(self, agent_run_id: UUID, call_id: str) -> ToolCallRecord | None:
        result = await self.session.execute(
            select(ToolCallRecord).where(
                ToolCallRecord.agent_run_id == agent_run_id,
                ToolCallRecord.call_id == call_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        agent_run_id: UUID,
        call_id: str,
        tool_name: str,
        arguments: dict[str, object] | None = None,
    ) -> ToolCallRecord:
        record = ToolCallRecord(
            agent_run_id=agent_run_id,
            call_id=call_id,
            tool_name=tool_name,
            status=ToolCallStatus.PENDING,
            arguments=arguments,
        )
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def update_status(
        self,
        record: ToolCallRecord,
        *,
        status: ToolCallStatus,
        result: object | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        duration_ms: float | None = None,
    ) -> ToolCallRecord:
        record.status = status
        record.result = result
        record.error_code = error_code
        record.error_message = error_message
        record.duration_ms = duration_ms
        if status == ToolCallStatus.RUNNING and record.started_at is None:
            record.started_at = datetime.now(UTC)
        if status in {
            ToolCallStatus.COMPLETED,
            ToolCallStatus.FAILED,
            ToolCallStatus.CANCELLED,
        }:
            record.finished_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(record)
        return record
