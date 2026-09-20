"""Unit tests for bounded short-term conversation memory."""

import pytest

from app.memory.short_term import MemoryMessage, ShortTermMemory


def test_memory_selects_newest_contiguous_messages_within_token_budget() -> None:
    memory = ShortTermMemory(max_messages=4, token_budget=5, chars_per_token=4)

    window = memory.select(
        [
            MemoryMessage(role="user", content="old message"),
            MemoryMessage(role="assistant", content="recent answer"),
            MemoryMessage(role="user", content="new question"),
        ]
    )

    assert window.messages == (
        MemoryMessage(role="user", content="new question"),
    )
    assert window.used_tokens == 3


def test_memory_truncates_one_oversized_newest_message() -> None:
    memory = ShortTermMemory(max_messages=4, token_budget=2, chars_per_token=4)

    window = memory.select([MemoryMessage(role="assistant", content="123456789")])

    assert window.messages[0].content == "12345678"
    assert window.used_tokens == 2


@pytest.mark.parametrize(
    ("max_messages", "token_budget"),
    [(0, 10), (1, 0)],
)
def test_memory_rejects_invalid_limits(max_messages: int, token_budget: int) -> None:
    with pytest.raises(ValueError):
        ShortTermMemory(max_messages=max_messages, token_budget=token_budget)
