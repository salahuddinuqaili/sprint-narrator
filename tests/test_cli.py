from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from sprint_narrator.aggregator import WorkItem
from sprint_narrator.cli import app
from sprint_narrator.config import AppConfig
from sprint_narrator.exceptions import SourceAuthError, SourceFetchError

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
        linear_token=kwargs.get("linear_token"),
        linear_team_id=kwargs.get("linear_team_id"),
    )


def _mock_github_items() -> list[WorkItem]:
    return [
        _make_item("Add login page", labels=["feature"]),
        _make_item("Fix crash on startup", labels=["bug"]),
        _make_item("Refactor auth module"),
    ]


def _mock_linear_items() -> list[WorkItem]:
    return [
        _make_item("Design dashboard", source="linear", labels=["feature"]),
        _make_item("Fix typo in docs", source="linear", labels=["bug"]),
    ]


# --- Existing tests ---


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

    result = runner.invoke(
        app,
        [
            "run",
            "-s",
            "github",
            "--since",
            "2026-05-01",
            "--until",
            "2026-05-14",
        ],
    )

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

    result = runner.invoke(
        app,
        [
            "run",
            "-s",
            "github",
            "--since",
            "2026-05-01",
            "--until",
            "2026-05-14",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "LLM unavailable" in result.stdout
    assert "fallback" in result.stdout.lower()
    mock_fallback.assert_called_once()


@patch("sprint_narrator.cli.load_config")
def test_run_command_no_source(mock_config: MagicMock) -> None:
    """Error when source token is not configured."""
    mock_config.return_value = AppConfig()  # No tokens set

    result = runner.invoke(
        app,
        [
            "run",
            "-s",
            "github",
            "--since",
            "2026-05-01",
            "--until",
            "2026-05-14",
        ],
    )

    assert result.exit_code != 0


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


# --- New Phase 6 tests ---


@patch("sprint_narrator.cli.load_config")
@patch("sprint_narrator.cli._fetch_github", new_callable=AsyncMock)
@patch("sprint_narrator.narrator.generate_narrative", new_callable=AsyncMock)
def test_run_dry_run(
    mock_narrate: AsyncMock,
    mock_fetch: AsyncMock,
    mock_config: MagicMock,
) -> None:
    """--dry-run shows stats table without calling narrator."""
    mock_config.return_value = _make_config()
    mock_fetch.return_value = _mock_github_items()

    result = runner.invoke(
        app,
        [
            "run",
            "-s",
            "github",
            "--since",
            "2026-05-01",
            "--until",
            "2026-05-14",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "dry run" in result.stdout.lower()
    # Stats table should show categories
    assert "Features" in result.stdout
    assert "Bug Fixes" in result.stdout
    # Narrator should NOT be called
    mock_narrate.assert_not_called()


@patch("sprint_narrator.cli.load_config")
@patch("sprint_narrator.cli._fetch_github", new_callable=AsyncMock)
def test_run_auth_error_display(
    mock_fetch: AsyncMock,
    mock_config: MagicMock,
) -> None:
    """Source auth failure shows actionable error message."""
    mock_config.return_value = _make_config()
    mock_fetch.side_effect = SourceAuthError("GitHub authentication failed.")

    result = runner.invoke(
        app,
        [
            "run",
            "-s",
            "github",
            "--since",
            "2026-05-01",
            "--until",
            "2026-05-14",
        ],
    )

    assert "authentication failed" in result.stdout.lower()
    assert "configure" in result.stdout.lower()


@patch("sprint_narrator.cli.load_config")
@patch("sprint_narrator.cli._fetch_github", new_callable=AsyncMock)
@patch("sprint_narrator.cli._fetch_linear", new_callable=AsyncMock)
@patch("sprint_narrator.narrator.generate_narrative", new_callable=AsyncMock)
def test_run_multiple_sources(
    mock_narrate: AsyncMock,
    mock_linear: AsyncMock,
    mock_github: AsyncMock,
    mock_config: MagicMock,
) -> None:
    """Multiple sources are fetched concurrently."""
    mock_config.return_value = _make_config(linear_token="lin_test", linear_team_id="team-1")
    mock_github.return_value = _mock_github_items()
    mock_linear.return_value = _mock_linear_items()
    mock_narrate.return_value = "## Executive Summary\nGreat sprint!"

    result = runner.invoke(
        app,
        [
            "run",
            "-s",
            "github",
            "-s",
            "linear",
            "--since",
            "2026-05-01",
            "--until",
            "2026-05-14",
        ],
    )

    assert result.exit_code == 0, result.stdout
    # Both sources should be fetched
    mock_github.assert_called_once()
    mock_linear.assert_called_once()
    assert "Github" in result.stdout
    assert "Linear" in result.stdout


@patch("sprint_narrator.cli.load_config")
@patch("sprint_narrator.cli._fetch_github", new_callable=AsyncMock)
@patch("sprint_narrator.cli._fetch_linear", new_callable=AsyncMock)
@patch("sprint_narrator.narrator.generate_narrative", new_callable=AsyncMock)
def test_run_source_partial_failure(
    mock_narrate: AsyncMock,
    mock_linear: AsyncMock,
    mock_github: AsyncMock,
    mock_config: MagicMock,
) -> None:
    """One source fails, other succeeds — partial results are used."""
    mock_config.return_value = _make_config(linear_token="lin_test", linear_team_id="team-1")
    mock_github.return_value = _mock_github_items()
    mock_linear.side_effect = SourceFetchError("Linear API timeout")
    mock_narrate.return_value = "## Executive Summary\nGood sprint despite issues."

    result = runner.invoke(
        app,
        [
            "run",
            "-s",
            "github",
            "-s",
            "linear",
            "--since",
            "2026-05-01",
            "--until",
            "2026-05-14",
        ],
    )

    assert result.exit_code == 0, result.stdout
    # GitHub succeeded
    assert "Github" in result.stdout
    assert "fetched" in result.stdout
    # Linear failed but didn't block the pipeline
    assert "Linear" in result.stdout
    # Narrative was still generated from GitHub data
    mock_narrate.assert_called_once()


# --- Demo command ---


def test_demo_command() -> None:
    """Demo runs without error and contains expected sections."""
    result = runner.invoke(app, ["demo"])

    assert result.exit_code == 0, result.stdout
    assert "demo" in result.stdout.lower()
    # Should contain sample data
    assert "SSO" in result.stdout or "login" in result.stdout.lower()
    # Should contain sprint summary structure
    assert "Sprint Summary" in result.stdout
    assert "Shipped" in result.stdout
