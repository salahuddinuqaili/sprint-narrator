from unittest.mock import AsyncMock, MagicMock

import pytest

from sprint_narrator.aggregator import SprintData, WorkItem
from sprint_narrator.exceptions import NarratorError
from sprint_narrator.narrator import (
    _format_sprint_context,
    _get_model_tier,
    check_ollama_health,
    generate_fallback_narrative,
    generate_narrative,
)


def _make_item(
    title: str = "Test item",
    description: str = "A test description that is reasonably long for testing",
    status: str = "closed",
    **kwargs,
) -> WorkItem:
    return WorkItem(
        title=title,
        description=description,
        status=status,
        assignee=kwargs.get("assignee", "dev"),
        source=kwargs.get("source", "github"),
        url=kwargs.get("url", "https://github.com/test/1"),
        labels=kwargs.get("labels", []),
    )


def _make_sprint_data(
    features: int = 5,
    bugs: int = 2,
    in_progress: int = 3,
    blocked: int = 1,
) -> SprintData:
    return SprintData(
        features=[_make_item(title=f"Feature {i + 1}") for i in range(features)],
        bug_fixes=[_make_item(title=f"Bug fix {i + 1}") for i in range(bugs)],
        in_progress=[_make_item(title=f"In progress {i + 1}") for i in range(in_progress)],
        blocked=[_make_item(title=f"Blocked {i + 1}") for i in range(blocked)],
        other=[],
        stats={"total": features + bugs + in_progress + blocked},
    )


# --- check_ollama_health ---


def test_check_ollama_health_not_running(monkeypatch):
    """ConnectionError from ollama.list() raises NarratorError."""
    monkeypatch.setattr(
        "sprint_narrator.narrator.ollama.list",
        MagicMock(side_effect=ConnectionError("refused")),
    )
    with pytest.raises(NarratorError, match="Ollama is not running"):
        check_ollama_health("llama3.1:8b")


def test_check_ollama_health_model_missing(monkeypatch):
    """Missing model raises NarratorError with pull instructions."""
    model_obj = MagicMock()
    model_obj.model = "mistral:latest"
    response = MagicMock()
    response.models = [model_obj]
    monkeypatch.setattr(
        "sprint_narrator.narrator.ollama.list",
        MagicMock(return_value=response),
    )
    with pytest.raises(NarratorError, match="Model 'llama3.1:8b' not found"):
        check_ollama_health("llama3.1:8b")


def test_check_ollama_health_success(monkeypatch):
    """Health check passes when model is available."""
    model_obj = MagicMock()
    model_obj.model = "llama3.1:8b"
    response = MagicMock()
    response.models = [model_obj]
    monkeypatch.setattr(
        "sprint_narrator.narrator.ollama.list",
        MagicMock(return_value=response),
    )
    check_ollama_health("llama3.1:8b")  # Should not raise


# --- _get_model_tier ---


@pytest.mark.parametrize(
    "model,expected",
    [
        ("phi3", "small"),
        ("gemma2:2b", "small"),
        ("qwen2:1.5b", "small"),
        ("llama3.1:8b", "medium"),
        ("mistral", "medium"),
        ("gemma2:9b", "medium"),
        ("llama3.1:70b", "large"),
        ("mixtral", "large"),
    ],
)
def test_get_model_tier_known(model: str, expected: str):
    """Known models are classified correctly."""
    assert _get_model_tier(model) == expected


def test_get_model_tier_unknown():
    """Unknown models default to medium."""
    assert _get_model_tier("some-custom-model") == "medium"


def test_get_model_tier_parses_size():
    """Models with size in name are parsed correctly."""
    assert _get_model_tier("custom:2b") == "small"
    assert _get_model_tier("custom:13b") == "large"


# --- _format_sprint_context ---


def test_format_sprint_context_small_model():
    """Small model tier: titles only, max 20 items."""
    data = _make_sprint_data()
    context = _format_sprint_context(data, "small", "", "")

    assert "SHIPPED (5):" in context
    assert "BUG FIXES (2):" in context
    assert "IN PROGRESS (3):" in context
    assert "BLOCKED (1):" in context
    # Titles should appear
    assert "Feature 1" in context
    # Descriptions should NOT appear for small tier
    assert "A test description" not in context


def test_format_sprint_context_medium_model():
    """Medium model tier: titles + short descriptions."""
    data = _make_sprint_data(features=1)
    context = _format_sprint_context(data, "medium", "", "")

    assert "SHIPPED (1):" in context
    # Description should appear (truncated to 50 chars)
    assert "Feature 1" in context
    assert "A test description" in context


def test_format_sprint_context_truncates():
    """Descriptions are truncated to tier-appropriate length."""
    long_desc = "x" * 200
    data = SprintData(
        features=[_make_item(title="Long item", description=long_desc)],
        bug_fixes=[],
        in_progress=[],
        blocked=[],
        other=[],
        stats={},
    )

    # Medium tier truncates to 50 chars
    context = _format_sprint_context(data, "medium", "", "")
    # Find the line with the item
    for line in context.split("\n"):
        if "Long item" in line:
            # Description part should be truncated (50 chars including "...")
            desc_part = line.split(" — ")[1]
            assert len(desc_part) == 50
            assert desc_part.endswith("...")
            break


def test_format_sprint_context_max_items():
    """Small tier limits to 20 items per category."""
    data = _make_sprint_data(features=25)
    context = _format_sprint_context(data, "small", "", "")

    assert "SHIPPED (25):" in context  # Count shows all items
    # But only 20 items rendered
    assert "Feature 20" in context
    assert "Feature 21" not in context


def test_format_sprint_context_with_dates():
    """Date range is included when provided."""
    data = _make_sprint_data(features=1, bugs=0, in_progress=0, blocked=0)
    context = _format_sprint_context(data, "medium", "2026-05-01", "2026-05-14")

    assert "SPRINT PERIOD: from 2026-05-01 to 2026-05-14" in context


def test_format_sprint_context_stats():
    """Stats line shows completion rate."""
    data = _make_sprint_data(features=5, bugs=2, in_progress=3, blocked=1)
    context = _format_sprint_context(data, "medium", "", "")

    assert "STATS: 7/11 items completed (64% completion rate)" in context


# --- generate_narrative ---


@pytest.mark.asyncio
async def test_generate_narrative_success(monkeypatch):
    """Successful narrative generation returns LLM content."""
    # Mock health check
    model_obj = MagicMock()
    model_obj.model = "llama3.1:8b"
    list_response = MagicMock()
    list_response.models = [model_obj]
    monkeypatch.setattr(
        "sprint_narrator.narrator.ollama.list",
        MagicMock(return_value=list_response),
    )

    # Mock AsyncClient.chat()
    mock_chat = AsyncMock(
        return_value={"message": {"content": "## Executive Summary\nGreat sprint!"}}
    )
    mock_client = MagicMock()
    mock_client.chat = mock_chat
    monkeypatch.setattr(
        "sprint_narrator.narrator.ollama.AsyncClient",
        MagicMock(return_value=mock_client),
    )

    data = _make_sprint_data()
    result = await generate_narrative(data, model="llama3.1:8b")

    assert "Great sprint!" in result
    mock_chat.assert_called_once()
    call_kwargs = mock_chat.call_args
    assert call_kwargs.kwargs["model"] == "llama3.1:8b"
    assert call_kwargs.kwargs["options"]["temperature"] == 0.3
    assert call_kwargs.kwargs["options"]["num_ctx"] == 4096


@pytest.mark.asyncio
async def test_generate_narrative_ollama_error(monkeypatch):
    """Ollama ResponseError is wrapped in NarratorError."""
    import ollama as ollama_lib

    # Mock health check
    model_obj = MagicMock()
    model_obj.model = "llama3.1:8b"
    list_response = MagicMock()
    list_response.models = [model_obj]
    monkeypatch.setattr(
        "sprint_narrator.narrator.ollama.list",
        MagicMock(return_value=list_response),
    )

    # Mock AsyncClient.chat() to raise ResponseError
    mock_chat = AsyncMock(side_effect=ollama_lib.ResponseError("model error"))
    mock_client = MagicMock()
    mock_client.chat = mock_chat
    monkeypatch.setattr(
        "sprint_narrator.narrator.ollama.AsyncClient",
        MagicMock(return_value=mock_client),
    )

    data = _make_sprint_data()
    with pytest.raises(NarratorError, match="Ollama request failed"):
        await generate_narrative(data, model="llama3.1:8b")


# --- generate_fallback_narrative ---


def test_generate_fallback_narrative():
    """Fallback produces correct stats and structure."""
    data = _make_sprint_data(features=5, bugs=2, in_progress=3, blocked=1)
    result = generate_fallback_narrative(data)

    assert "7 of 11" in result
    assert "64%" in result
    assert "5 features shipped" in result
    assert "2 bugs were fixed" in result
    assert "1 item is blocked" in result
    assert "3 items are still in progress" in result


def test_generate_fallback_narrative_empty():
    """Fallback handles empty sprint data."""
    data = _make_sprint_data(features=0, bugs=0, in_progress=0, blocked=0)
    result = generate_fallback_narrative(data)

    assert "0 of 0" in result
    assert "0%" in result


def test_generate_fallback_narrative_singular():
    """Fallback uses correct singular/plural forms."""
    data = _make_sprint_data(features=1, bugs=1, in_progress=1, blocked=0)
    result = generate_fallback_narrative(data)

    assert "1 feature shipped" in result
    assert "1 bug was fixed" in result
    assert "1 item is still in progress" in result
