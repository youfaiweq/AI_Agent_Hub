"""Unit tests for explicit long-term memory extraction."""

from app.memory.long_term import ExplicitMemoryExtractor


def test_extractor_accepts_explicit_english_request() -> None:
    result = ExplicitMemoryExtractor().extract("Please remember that I prefer concise updates.")

    assert len(result) == 1
    assert result[0].content == "I prefer concise updates."
    assert result[0].source == "explicit_user"


def test_extractor_accepts_explicit_chinese_request() -> None:
    result = ExplicitMemoryExtractor().extract("请记住：我喜欢清晰的步骤。")

    assert len(result) == 1
    assert result[0].content == "我喜欢清晰的步骤。"


def test_extractor_does_not_promote_ordinary_chat_to_memory() -> None:
    result = ExplicitMemoryExtractor().extract("I prefer concise updates.")

    assert result == []
