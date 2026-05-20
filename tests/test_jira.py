from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from sprint_narrator.exceptions import SourceAuthError, SourceFetchError
from sprint_narrator.sources.jira import JiraSource


def _make_issue(
    key: str = "PROJ-1",
    summary: str = "Add login page",
    status: str = "Done",
    assignee: str = "Alice",
    description: str = "Build the login flow",
    resolution_date: str | None = "2026-05-12T10:00:00+00:00",
    labels: list[str] | None = None,
) -> dict:
    """Factory for Jira search response issues."""
    return {
        "key": key,
        "fields": {
            "summary": summary,
            "description": description,
            "status": {"name": status},
            "assignee": {"displayName": assignee} if assignee else None,
            "resolutiondate": resolution_date,
            "labels": labels or [],
        },
    }


def _make_search_response(
    issues: list[dict],
    total: int | None = None,
    start_at: int = 0,
) -> dict:
    """Build a Jira search API response."""
    if total is None:
        total = len(issues)
    return {
        "issues": issues,
        "total": total,
        "startAt": start_at,
        "maxResults": 100,
    }


def _mock_response(
    status_code: int = 200,
    json_data: dict | None = None,
) -> httpx.Response:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


@pytest.fixture()
def since() -> datetime:
    return datetime(2026, 5, 10, tzinfo=UTC)


@pytest.fixture()
def until() -> datetime:
    return datetime(2026, 5, 20, tzinfo=UTC)


@pytest.fixture()
def source() -> JiraSource:
    return JiraSource(
        url="https://test.atlassian.net",
        email="test@example.com",
        token="jira_token_123",
        project_key="PROJ",
    )


@pytest.mark.asyncio
async def test_fetch_issues_maps_to_work_items(
    source: JiraSource, since: datetime, until: datetime
) -> None:
    """Search response maps to correct WorkItem fields."""
    issue = _make_issue(labels=["feature"])
    source._client.get = AsyncMock(
        return_value=_mock_response(json_data=_make_search_response([issue]))
    )

    items = await source.fetch_issues(since, until)

    assert len(items) == 1
    item = items[0]
    assert item.title == "Add login page"
    assert item.status == "done"
    assert item.source == "jira"
    assert item.assignee == "Alice"
    assert item.url == "https://test.atlassian.net/browse/PROJ-1"
    assert "feature" in item.labels
    assert item.completed_at is not None
    await source.close()


@pytest.mark.asyncio
async def test_fetch_issues_jql_date_format(
    source: JiraSource, since: datetime, until: datetime
) -> None:
    """JQL query contains correctly formatted date strings."""
    source._client.get = AsyncMock(
        return_value=_mock_response(json_data=_make_search_response([]))
    )

    await source.fetch_issues(since, until)

    call_kwargs = source._client.get.call_args
    jql = call_kwargs.kwargs["params"]["jql"]
    assert '2026-05-10' in jql
    assert '2026-05-20' in jql
    assert 'project = "PROJ"' in jql
    await source.close()


@pytest.mark.asyncio
async def test_fetch_issues_paginates(
    source: JiraSource, since: datetime, until: datetime
) -> None:
    """Offset-based pagination fetches multiple pages."""
    page1 = _make_search_response(
        [_make_issue(key="PROJ-1", summary="Issue 1")],
        total=2,
        start_at=0,
    )
    page2 = _make_search_response(
        [_make_issue(key="PROJ-2", summary="Issue 2")],
        total=2,
        start_at=1,
    )

    source._client.get = AsyncMock(side_effect=[
        _mock_response(json_data=page1),
        _mock_response(json_data=page2),
    ])

    items = await source.fetch_issues(since, until)

    assert len(items) == 2
    assert items[0].title == "Issue 1"
    assert items[1].title == "Issue 2"
    assert source._client.get.call_count == 2
    await source.close()


@pytest.mark.asyncio
async def test_fetch_issues_auth_error(
    source: JiraSource, since: datetime, until: datetime
) -> None:
    """401 response raises SourceAuthError."""
    source._client.get = AsyncMock(
        return_value=_mock_response(status_code=401)
    )

    with pytest.raises(SourceAuthError, match="authentication failed"):
        await source.fetch_issues(since, until)
    await source.close()


@pytest.mark.asyncio
async def test_fetch_issues_http_error(
    source: JiraSource, since: datetime, until: datetime
) -> None:
    """500 response raises SourceFetchError."""
    source._client.get = AsyncMock(
        return_value=_mock_response(status_code=500)
    )

    with pytest.raises(SourceFetchError, match="HTTP 500"):
        await source.fetch_issues(since, until)
    await source.close()


@pytest.mark.asyncio
async def test_fetch_issues_truncates_description(
    source: JiraSource, since: datetime, until: datetime
) -> None:
    """Long string descriptions are truncated to 200 characters."""
    issue = _make_issue(description="x" * 500)
    source._client.get = AsyncMock(
        return_value=_mock_response(json_data=_make_search_response([issue]))
    )

    items = await source.fetch_issues(since, until)

    assert len(items[0].description) == 200
    await source.close()


@pytest.mark.asyncio
async def test_fetch_issues_adf_description(
    source: JiraSource, since: datetime, until: datetime
) -> None:
    """ADF (Atlassian Document Format) descriptions are extracted as text."""
    adf = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Build the"},
                    {"type": "text", "text": "login flow"},
                ],
            }
        ],
    }
    issue = _make_issue()
    issue["fields"]["description"] = adf
    source._client.get = AsyncMock(
        return_value=_mock_response(json_data=_make_search_response([issue]))
    )

    items = await source.fetch_issues(since, until)

    assert items[0].description == "Build the login flow"
    await source.close()


@pytest.mark.asyncio
async def test_fetch_issues_no_assignee(
    source: JiraSource, since: datetime, until: datetime
) -> None:
    """Null assignee defaults to 'unassigned'."""
    issue = _make_issue(assignee="")
    source._client.get = AsyncMock(
        return_value=_mock_response(json_data=_make_search_response([issue]))
    )

    items = await source.fetch_issues(since, until)

    assert items[0].assignee == "unassigned"
    await source.close()


@pytest.mark.asyncio
async def test_fetch_issues_status_mapping(
    source: JiraSource, since: datetime, until: datetime
) -> None:
    """Jira statuses map to internal status values."""
    issues = [
        _make_issue(key="P-1", summary="Done", status="Done"),
        _make_issue(key="P-2", summary="Closed", status="Closed"),
        _make_issue(key="P-3", summary="Resolved", status="Resolved"),
        _make_issue(key="P-4", summary="WIP", status="In Progress"),
        _make_issue(key="P-5", summary="Stuck", status="Blocked"),
        _make_issue(key="P-6", summary="Todo", status="To Do"),
    ]
    source._client.get = AsyncMock(
        return_value=_mock_response(json_data=_make_search_response(issues))
    )

    items = await source.fetch_issues(since, until)
    statuses = {i.title: i.status for i in items}

    assert statuses["Done"] == "done"
    assert statuses["Closed"] == "done"
    assert statuses["Resolved"] == "done"
    assert statuses["WIP"] == "in_progress"
    assert statuses["Stuck"] == "blocked"
    assert statuses["Todo"] == "other"
    await source.close()


@pytest.mark.asyncio
async def test_fetch_sprint_success(
    source: JiraSource, since: datetime, until: datetime
) -> None:
    """Agile endpoints return sprint metadata."""
    board_response = _mock_response(json_data={
        "values": [{"id": 42, "name": "PROJ board"}],
    })
    sprint_response = _mock_response(json_data={
        "values": [
            {
                "name": "Sprint 5",
                "state": "active",
                "startDate": "2026-05-10T00:00:00.000Z",
                "endDate": "2026-05-24T00:00:00.000Z",
                "goal": "Ship login feature",
            },
            {
                "name": "Sprint 4",
                "state": "closed",
                "startDate": "2026-04-01T00:00:00.000Z",
                "endDate": "2026-04-15T00:00:00.000Z",
                "goal": "Setup project",
            },
        ],
    })

    source._client.get = AsyncMock(side_effect=[board_response, sprint_response])

    sprints = await source.fetch_sprint(since, until)

    # Only Sprint 5 overlaps the date range
    assert len(sprints) == 1
    assert sprints[0]["name"] == "Sprint 5"
    assert sprints[0]["state"] == "active"
    assert sprints[0]["goal"] == "Ship login feature"
    await source.close()


@pytest.mark.asyncio
async def test_fetch_sprint_agile_unavailable(
    source: JiraSource, since: datetime, until: datetime
) -> None:
    """Agile endpoint failure returns empty list gracefully."""
    source._client.get = AsyncMock(
        return_value=_mock_response(status_code=404)
    )

    sprints = await source.fetch_sprint(since, until)

    assert sprints == []
    await source.close()
