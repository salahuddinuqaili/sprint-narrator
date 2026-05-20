from datetime import UTC, datetime

from sprint_narrator.aggregator import SprintData, WorkItem
from sprint_narrator.render import render_output


def _make_item(title: str = "Test item", **kwargs) -> WorkItem:
    return WorkItem(
        title=title,
        description=kwargs.get("description", "A test description"),
        status=kwargs.get("status", "done"),
        assignee=kwargs.get("assignee", "dev"),
        source=kwargs.get("source", "github"),
        url=kwargs.get("url", "https://github.com/test/1"),
        completed_at=kwargs.get("completed_at", datetime(2026, 5, 10, tzinfo=UTC)),
        labels=kwargs.get("labels", []),
    )


def _make_sprint_data() -> SprintData:
    return SprintData(
        features=[_make_item("Login page"), _make_item("Dashboard")],
        bug_fixes=[_make_item("Fix crash")],
        in_progress=[_make_item("API refactor", status="in progress")],
        blocked=[],
        other=[],
        stats={
            "total": 4,
            "completed": 3,
            "completion_rate": "75%",
            "contributors": ["dev"],
        },
    )


def test_render_output_markdown() -> None:
    """Markdown template renders with all sections."""
    data = _make_sprint_data()
    result = render_output(
        narrative="Great sprint!",
        sprint_data=data,
        fmt="md",
        since="2026-05-01",
        until="2026-05-14",
        sources=["github"],
    )

    assert "Sprint Summary" in result
    assert "2026-05-01" in result
    assert "2026-05-14" in result
    assert "Great sprint!" in result
    assert "Login page" in result
    assert "Fix crash" in result
    assert "API refactor" in result
    assert "github" in result


def test_render_output_html() -> None:
    """HTML template renders with structure."""
    data = _make_sprint_data()
    result = render_output(
        narrative="Solid progress this sprint.",
        sprint_data=data,
        fmt="html",
        since="2026-05-01",
        until="2026-05-14",
        sources=["github"],
    )

    assert "<!DOCTYPE html>" in result
    assert "Solid progress this sprint." in result
    assert "Login page" in result
    assert "Fix crash" in result
    assert "75%" in result


def test_render_output_unknown_format() -> None:
    """Unknown format raises ValueError."""
    import pytest

    data = _make_sprint_data()
    with pytest.raises(ValueError, match="Unknown format"):
        render_output(
            narrative="test",
            sprint_data=data,
            fmt="pdf",
            since="2026-05-01",
            until="2026-05-14",
            sources=["github"],
        )
