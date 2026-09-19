"""Agent configuration persistence operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_config import Agent


class AgentRepository:
    """CRUD queries scoped to the authenticated user."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, **values: object) -> Agent:
        agent = Agent(**values)
        self.session.add(agent)
        await self.session.flush()
        await self.session.refresh(agent)
        return agent

    async def list_owned(self, user_id: UUID) -> list[Agent]:
        result = await self.session.execute(
            select(Agent)
            .where(Agent.user_id == user_id)
            .order_by(Agent.updated_at.desc(), Agent.id)
        )
        return list(result.scalars().all())

    async def get_owned(self, agent_id: UUID, user_id: UUID) -> Agent | None:
        result = await self.session.execute(
            select(Agent).where(Agent.id == agent_id, Agent.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def delete(self, agent: Agent) -> None:
        await self.session.delete(agent)
