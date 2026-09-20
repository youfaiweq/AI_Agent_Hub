"""Create repeatable, configuration-only AgentHub demo data.

The script never stores or prints the demo password. Set DEMO_USER_EMAIL and
DEMO_USER_PASSWORD in the local environment before running it.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.core.database import get_session_factory  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.agent_config import Agent  # noqa: E402
from app.models.knowledge_base import KnowledgeBase  # noqa: E402
from app.models.long_term_memory import LongTermMemory  # noqa: E402
from app.models.user import User  # noqa: E402


async def seed() -> None:
    email = os.environ.get("DEMO_USER_EMAIL", "demo@example.com").strip().lower()
    password = os.environ.get("DEMO_USER_PASSWORD", "")
    if not password:
        raise SystemExit("Set DEMO_USER_PASSWORD in the local environment before running the seed.")

    async with get_session_factory()() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            user = User(email=email, password_hash=hash_password(password))
            session.add(user)
            await session.flush()

        knowledge_base = (
            await session.execute(
                select(KnowledgeBase).where(
                    KnowledgeBase.user_id == user.id,
                    KnowledgeBase.name == "AgentHub Demo Knowledge Base",
                )
            )
        ).scalar_one_or_none()
        if knowledge_base is None:
            knowledge_base = KnowledgeBase(
                user_id=user.id,
                name="AgentHub Demo Knowledge Base",
                description="Seeded workspace for the v1.0 product walkthrough.",
            )
            session.add(knowledge_base)
            await session.flush()

        agent = (
            await session.execute(
                select(Agent).where(Agent.user_id == user.id, Agent.name == "Demo Research Agent")
            )
        ).scalar_one_or_none()
        if agent is None:
            session.add(
                Agent(
                    user_id=user.id,
                    knowledge_base_id=knowledge_base.id,
                    name="Demo Research Agent",
                    description="A bounded read-only Agent for the v1.0 walkthrough.",
                    system_prompt="Answer concisely and explain which read-only tool was useful.",
                    model_name="qwen-plus",
                    max_steps=5,
                    timeout_seconds=60.0,
                    tool_names=["knowledge_search", "calculator"],
                )
            )

        memory = (
            await session.execute(
                select(LongTermMemory).where(
                    LongTermMemory.user_id == user.id,
                    LongTermMemory.content == "The demo user prefers concise status updates.",
                )
            )
        ).scalar_one_or_none()
        if memory is None:
            session.add(
                LongTermMemory(
                    user_id=user.id,
                    content="The demo user prefers concise status updates.",
                    memory_type="preference",
                    source="user_confirmed",
                    confidence=1.0,
                )
            )

        await session.commit()
        print(f"Demo data ready for {email}. User, knowledge base, Agent, and confirmed memory are available.")


if __name__ == "__main__":
    asyncio.run(seed())
