from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from sprint_narrator.exceptions import SourceAuthError, SourceFetchError
from sprint_narrator.sources.linear import LinearSource


def _make_issue(
    title: str = "Implement login",
    state: str = "Done",
    assignee: str = "Alice",
    description: str = "Build the login flow",
    completed_at: str | None = "2026-05-12T10:00:00Z",
    labels: list[str] | None = None,
) -> dict:
    """Factory for Linear issue GraphQL response nodes."""
    return {
        "identifier": "ENG-123",
        "title": title,
        "description": description,
        "state": {"name": state},
        "assignee": {"displayName": assignee} if assignee else None,
        "completedAt": completed_at,
        "url": "https://linear.app/team/issue/ENG-123",
        "labels": {"nodes": [{"name": lbl} for lbl in (labels or [])]},
    }


def _make_graphql_response(
    nodes: list[dict],
    has_next_page: bool = False,
    end_cursor: str | None = None,
) -> dict:
    """Build a full GraphQL response body for issues."""
    return {
        "data": {
            "issues": {
                "nodes": nodes,
                "pageInfo": {
                    "hasNextPage": has_next_page,
                    "endCursor": end_cursor,
                },
            }
        }
    }


def _mock_response(
    status_code: int = 200,
    json_data: dict | None = None,
) -> httpx.Response:
    """Build a mock httpx.Response."""
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


@pytest.mark.asyncio
async def test_fetch_issues_maps_to_work_items(since: datetime, until: datetime) -> None:
    """GraphQL response nodes map to correct WorkItem fields."""
    source = LinearSource(token="lin_test", team_id="team-1")
    issue = _make_issue(labels=["feature", "frontend"])
    source._client.post = AsyncMock(
        return_value=_mock_response(json_data=_make_graphql_response([issue]))
    )

    items = await source.fetch_issues(since, until)

    assert len(items) == 1
    item = items[0]
    assert item.title == "Implement login"
    assert item.status == "done"
    assert item.source == "linear"
    assert item.assignee == "Alice"
    assert item.url == "https://linear.app/team/issue/ENG-123"
    assert "feature" in item.labels
    assert "frontend" in item.labels
    assert item.completed_at is not None
    await source.close()


@pytest.mark.asyncio
async def test_fetch_issues_state_mapping(since: datetime, until: datetime) -> None:
    """Linear states map to internal status values."""
    source = LinearSource(token="lin_test", team_id="team-1")
    issues = [
        _make_issue(title="Done item", state="Done"),
        _make_issue(title="Completed item", state="Completed"),
        _make_issue(title="WIP item", state="In Progress", completed_at=None),
        _make_issue(title="Started item", state="Started", completed_at=None),
        _make_issue(title="Blocked item", state="Blocked", completed_at=None),
        _make_issue(title="Backlog item", state="Backlog", completed_at=None),
    ]
    source._client.post = AsyncMock(
        return_value=_mock_response(json_data=_make_graphql_response(issues))
    )

    items = await source.fetch_issues(since, until)

    statuses = {i.title: i.status for i in items}
    assert statuses["Done item"] == "done"
    assert statuses["Completed item"] == "done"
    assert statuses["WIP item"] == "in_progress"
    assert statuses["Started item"] == "in_progress"
    assert statuses["Blocked item"] == "blocked"
    assert statuses["Backlog item"] == "other"
    await source.close()


@pytest.mark.asyncio
async def test_fetch_issues_paginates(since: datetime, until: datetime) -> None:
    """Cursor-based pagination fetches multiple pages."""
    source = LinearSource(token="lin_test", team_id="team-1")

    page1 = _make_graphql_response(
        [_make_issue(title="Issue 1")],
        has_next_page=True,
        end_cursor="cursor-abc",
    )
    page2 = _make_graphql_response(
        [_make_issue(title="Issue 2")],
        has_next_page=False,
    )

    source._client.post = AsyncMock(
        side_effect=[
            _mock_response(json_data=page1),
            _mock_response(json_data=page2),
        ]
    )

    items = await source.fetch_issues(since, until)

    assert len(items) == 2
    assert items[0].title == "Issue 1"
    assert items[1].title == "Issue 2"
    assert source._client.post.call_count == 2

    # Verify second call used the cursor
    second_call = source._client.post.call_args_list[1]
    variables = second_call.kwargs["json"]["variables"]
    assert variables["after"] == "cursor-abc"
    await source.close()


@pytest.mark.asyncio
async def test_fetch_issues_auth_error(since: datetime, until: datetime) -> None:
    """401 response raises SourceAuthError."""
    source = LinearSource(token="bad_token", team_id="team-1")
    source._client.post = AsyncMock(return_value=_mock_response(status_code=401))

    with pytest.raises(SourceAuthError, match="authentication failed"):
        await source.fetch_issues(since, until)
    await source.close()


@pytest.mark.asyncio
async def test_fetch_issues_graphql_error(since: datetime, until: datetime) -> None:
    """GraphQL errors field raises SourceFetchError."""
    source = LinearSource(token="lin_test", team_id="team-1")
    error_response = {"errors": [{"message": "Variable 'teamId' is invalid"}]}
    source._client.post = AsyncMock(return_value=_mock_response(json_data=error_response))

    with pytest.raises(SourceFetchError, match="Variable 'teamId' is invalid"):
        await source.fetch_issues(since, until)
    await source.close()


@pytest.mark.asyncio
async def test_fetch_issues_truncates_description(since: datetime, until: datetime) -> None:
    """Long descriptions are truncated to 200 characters."""
    source = LinearSource(token="lin_test", team_id="team-1")
    issue = _make_issue(description="x" * 500)
    source._client.post = AsyncMock(
        return_value=_mock_response(json_data=_make_graphql_response([issue]))
    )

    items = await source.fetch_issues(since, until)

    assert len(items[0].description) == 200
    await source.close()


@pytest.mark.asyncio
async def test_fetch_issues_no_assignee(since: datetime, until: datetime) -> None:
    """Issues without an assignee default to 'unassigned'."""
    source = LinearSource(token="lin_test", team_id="team-1")
    issue = _make_issue(assignee="")
    source._client.post = AsyncMock(
        return_value=_mock_response(json_data=_make_graphql_response([issue]))
    )

    items = await source.fetch_issues(since, until)

    assert items[0].assignee == "unassigned"
    await source.close()


@pytest.mark.asyncio
async def test_fetch_cycles(since: datetime, until: datetime) -> None:
    """Cycle query returns structured cycle data."""
    source = LinearSource(token="lin_test", team_id="team-1")
    cycle_response = {
        "data": {
            "team": {
                "cycles": {
                    "nodes": [
                        {
                            "name": "Sprint 12",
                            "number": 12,
                            "startsAt": "2026-05-10T00:00:00Z",
                            "endsAt": "2026-05-24T00:00:00Z",
                            "progress": 0.65,
                            "completedScopeCount": 8,
                            "scopeCount": 12,
                        },
                        {
                            "name": None,
                            "number": 11,
                            "startsAt": "2026-04-01T00:00:00Z",
                            "endsAt": "2026-04-15T00:00:00Z",
                            "progress": 1.0,
                            "completedScopeCount": 10,
                            "scopeCount": 10,
                        },
                    ]
                }
            }
        }
    }
    source._client.post = AsyncMock(return_value=_mock_response(json_data=cycle_response))

    cycles = await source.fetch_cycles(since, until)

    # Only Sprint 12 overlaps the date range
    assert len(cycles) == 1
    assert cycles[0]["name"] == "Sprint 12"
    assert cycles[0]["progress"] == 0.65
    assert cycles[0]["completed_scope"] == 8
    assert cycles[0]["total_scope"] == 12
    await source.close()
