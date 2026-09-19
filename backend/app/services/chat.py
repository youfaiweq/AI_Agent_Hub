"""Conversation and retrieval-grounded chat service."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.conversation import Conversation, Message
from app.rag.context.builder import Citation, ContextBuilder
from app.rag.llms.base import LLMError, LLMMessage, LLMProvider
from app.rag.retrievers.dense import DenseRetriever
from app.repositories.conversations import ConversationRepository, MessageRepository
from app.repositories.knowledge_bases import KnowledgeBaseRepository
from app.schemas.conversation import (
    ChatResponse,
    CitationResponse,
    ConversationCreate,
    ConversationResponse,
    MessageListResponse,
    MessageResponse,
)

NO_CONTEXT_ANSWER = "I couldn't confirm an answer from the knowledge base."
SYSTEM_PROMPT = (
    "Answer only from the supplied knowledge-base context. If the context does not support "
    "the answer, say that you cannot confirm it from the knowledge base."
)


class ChatService:
    def __init__(self, session: AsyncSession, retriever: DenseRetriever, llm: LLMProvider) -> None:
        self.session = session
        self.retriever = retriever
        self.llm = llm
        self.conversations = ConversationRepository(session)
        self.messages = MessageRepository(session)
        self.knowledge_bases = KnowledgeBaseRepository(session)
        self.context_builder = ContextBuilder()

    async def create_conversation(self, user_id: UUID, payload: ConversationCreate) -> ConversationResponse:
        knowledge_base = await self.knowledge_bases.get_owned(payload.knowledge_base_id, user_id)
        if knowledge_base is None:
            raise AppError("KNOWLEDGE_BASE_NOT_FOUND", "Knowledge base was not found", 404)
        conversation = await self.conversations.create(
            user_id,
            payload.knowledge_base_id,
            payload.title,
        )
        await self.session.commit()
        return ConversationResponse.model_validate(conversation)

    async def list_conversations(self, user_id: UUID) -> list[ConversationResponse]:
        items = await self.conversations.list_owned(user_id)
        return [ConversationResponse.model_validate(item) for item in items]

    async def get_conversation(self, user_id: UUID, conversation_id: UUID) -> Conversation:
        conversation = await self.conversations.get_owned(conversation_id, user_id)
        if conversation is None:
            raise AppError("CONVERSATION_NOT_FOUND", "Conversation was not found", 404)
        return conversation

    async def list_messages(self, user_id: UUID, conversation_id: UUID) -> MessageListResponse:
        conversation = await self.get_conversation(user_id, conversation_id)
        items = await self.messages.list_for_conversation(conversation.id)
        return MessageListResponse(items=[self._message_response(item) for item in items])

    async def delete_conversation(self, user_id: UUID, conversation_id: UUID) -> None:
        conversation = await self.get_conversation(user_id, conversation_id)
        await self.conversations.delete(conversation)
        await self.session.commit()

    async def chat(self, user_id: UUID, conversation_id: UUID, message: str) -> ChatResponse:
        conversation = await self.get_conversation(user_id, conversation_id)
        await self.messages.create(conversation.id, "user", message)
        await self.session.commit()

        try:
            retrieved = await self.retriever.retrieve(
                conversation.knowledge_base_id,
                message,
                top_k=5,
                score_threshold=get_settings().retrieval_score_threshold,
            )
        except Exception as exc:
            raise AppError("RETRIEVAL_FAILED", "Knowledge retrieval failed", 502) from exc

        context = self.context_builder.build(retrieved)
        citations = [self._citation_response(citation) for citation in context.citations]
        if not citations:
            answer = NO_CONTEXT_ANSWER
        else:
            history = await self.messages.list_for_conversation(conversation.id)
            prompt = f"Knowledge-base context:\n{context.text}\n\nUser question:\n{message}"
            llm_messages = [LLMMessage(role="system", content=SYSTEM_PROMPT)]
            llm_messages.extend(
                LLMMessage(role=item.role, content=item.content)
                for item in history[:-1]
                if item.role in {"user", "assistant"}
            )
            llm_messages.append(LLMMessage(role="user", content=prompt))
            try:
                response = await self.llm.generate(llm_messages)
            except LLMError as exc:
                raise AppError("LLM_GENERATION_FAILED", exc.message, 502) from exc
            if not response.content.strip():
                raise AppError("LLM_EMPTY_RESPONSE", "LLM provider returned an empty response", 502)
            answer = response.content.strip()

        assistant_message = await self.messages.create(
            conversation.id,
            "assistant",
            answer,
            [citation.model_dump() for citation in citations],
        )
        await self.session.commit()
        return ChatResponse(
            conversation=ConversationResponse.model_validate(conversation),
            message=self._message_response(assistant_message),
            citations=citations,
        )

    @staticmethod
    def _citation_response(citation: Citation) -> CitationResponse:
        return CitationResponse(
            citation_id=citation.citation_id,
            document_id=citation.document_id,
            filename=citation.filename,
            chunk_id=citation.chunk_id,
            page_number=citation.page_number,
            snippet=citation.snippet,
        )

    @staticmethod
    def _message_response(message: Message) -> MessageResponse:
        return MessageResponse(
            id=message.id,
            conversation_id=message.conversation_id,
            role=message.role,
            content=message.content,
            citations=[CitationResponse.model_validate(item) for item in (message.citations or [])],
            created_at=message.created_at,
            updated_at=message.updated_at,
        )
