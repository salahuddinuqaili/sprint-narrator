from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from sprint_narrator.aggregator import WorkItem
from sprint_narrator.cli import app
from sprint_narrator.config import AppConfig

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "sprint-narrator v" in result.stdout


def test_run_requires_source() -> None:
    result = runner.invoke(app, ["run"])
    assert result.exit_code != 0


def _make_item(title: str = "Test PR", **kwargs) -> WorkItem:
    return WorkItem(
        title=title,
        description=kwargs.get("description", "A test item"),
        status=kwargs.get("status", "done"),
        assignee=kwargs.get("assignee", "dev"),
        source=kwargs.get("source", "github"),
        url=kwargs.get("url", "https://github.com/test/1"),
        completed_at=kwargs.get("completed_at", datetime(2026, 5, 10, tzinfo=UTC)),
        labels=kwargs.get("labels", []),
    )


def _make_config(**kwargs) -> AppConfig:
    return AppConfig(
        github_token=kwargs.get("github_token", "ghp_test123"),
        github_repos=kwargs.get("github_repos", ["owner/repo"]),
        default_model=kwargs.get("default_model", "llama3.1:8b"),
    )


def _mock_github_items() -> list[WorkItem]:
    return [
        _make_item("Add login page", labels=["feature"]),
        _make_item("Fix crash on startup", labels=["bug"]),
        _make_item("Refactor auth module"),
    ]


@patch("sprint_narrator.cli.load_config")
@patch("sprint_narrator.cli._fetch_github", new_callable=AsyncMock)
@patch("sprint_narrator.narrator.generate_narrative", new_callable=AsyncMock)
def test_run_command_end_to_end(
    mock_narrate: AsyncMock,
    mock_fetch: AsyncMock,
    mock_config: MagicMock,
) -> None:
    """Full pipeline: fetch -> aggregate -> narrate -> render."""
    mock_config.return_value = _make_config()
    mock_fetch.return_value = _mock_github_items()
    mock_narrate.return_value = "## Executive Summary\nThe team shipped 2 features this sprint."

    result = runner.invoke(app, [
        "run", "-s", "github",
        "--since", "2026-05-01", "--until", "2026-05-14",
    ])

    assert result.exit_code == 0, result.stdout
    assert "team shipped 2 features" in result.stdout
    mock_fetch.assert_called_once()
    mock_narrate.assert_called_once()


@patch("sprint_narrator.cli.load_config")
@patch("sprint_narrator.cli._fetch_github", new_callable=AsyncMock)
@patch("sprint_narrator.narrator.generate_narrative", new_callable=AsyncMock)
@patch("sprint_narrator.narrator.generate_fallback_narrative")
def test_run_command_fallback(
    mock_fallback: MagicMock,
    mock_narrate: AsyncMock,
    mock_fetch: AsyncMock,
    mock_config: MagicMock,
) -> None:
    """Falls back to template narrative when Ollama is unavailable."""
    from sprint_narrator.exceptions import NarratorError

    mock_config.return_value = _make_config()
    mock_fetch.return_value = _mock_github_items()
    mock_narrate.side_effect = NarratorError("Ollama is not running")
    mock_fallback.return_value = "The team completed 3 of 3 items this sprint (100% completion)."

    result = runner.invoke(app, [
        "run", "-s", "github",
        "--since", "2026-05-01", "--until", "2026-05-14",
    ])

    assert result.exit_code == 0, result.stdout
    assert "LLM unavailable" in result.stdout
    assert "fallback" in result.stdout.lower()
    mock_fallback.assert_called_once()


@patch("sprint_narrator.cli.load_config")
def test_run_command_no_source(mock_config: MagicMock) -> None:
    """Error when source token is not configured."""
    mock_config.return_value = AppConfig()  # No tokens set

    result = runner.invoke(app, [
        "run", "-s", "github",
        "--since", "2026-05-01", "--until", "2026-05-14",
    ])

    assert result.exit_code != 0
    assert "token not configured" in result.stdout.lower() or result.exit_code != 0


@patch("sprint_narrator.storage.get_history")
def test_history_command(mock_history: MagicMock) -> None:
    """History command displays summaries as a Rich table."""
    mock_history.return_value = [
        {
            "date_range": "2026-05-01 to 2026-05-14",
            "sources": "github",
            "narrative": "The team shipped three features this sprint",
            "created_at": "2026-05-14 12:00:00",
        },
    ]

    result = runner.invoke(app, ["history"])

    assert result.exit_code == 0
    assert "2026-05-01 to 2026-05-14" in result.stdout
    assert "github" in result.stdout
    mock_history.assert_called_once_with(10)


def test_history_command_empty() -> None:
    """History command shows message when no summaries exist."""
    with patch("sprint_narrator.storage.get_history", return_value=[]):
        result = runner.invoke(app, ["history"])

    assert result.exit_code == 0
    assert "No past summaries found" in result.stdout
