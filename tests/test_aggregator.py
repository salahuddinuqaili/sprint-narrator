from datetime import datetime

from sprint_narrator.aggregator import WorkItem, aggregate


def _make_item(title: str, status: str = "done", labels: list[str] | None = None) -> WorkItem:
    return WorkItem(
        title=title,
        description="",
        status=status,
        assignee="dev",
        source="github",
        url="https://github.com/test",
        completed_at=datetime.now() if status == "done" else None,
        labels=labels or [],
    )


def test_aggregate_deduplicates() -> None:
    items = [_make_item("Add login"), _make_item("Add Login")]
    result = aggregate(items)
    assert result.stats["total"] == 1


def test_aggregate_categorizes_bugs() -> None:
    items = [_make_item("Fix crash", labels=["bug"])]
    result = aggregate(items)
    assert len(result.bug_fixes) == 1
    assert len(result.features) == 0


def test_aggregate_detects_blocked() -> None:
    items = [_make_item("Waiting on API", status="blocked")]
    result = aggregate(items)
    assert len(result.blocked) == 1
