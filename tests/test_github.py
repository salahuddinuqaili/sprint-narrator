from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from sprint_narrator.exceptions import SourceAuthError, SourceFetchError
from sprint_narrator.sources.github import GitHubSource


def _make_pr(
    title: str = "Add feature",
    merged_at: str | None = "2026-05-15T10:00:00Z",
    labels: list[dict] | None = None,
    login: str = "dev1",
) -> dict:
    """Factory for GitHub PR API responses."""
    return {
        "title": title,
        "body": "Some description of changes",
        "merged_at": merged_at,
        "html_url": "https://github.com/owner/repo/pull/1",
        "user": {"login": login},
        "labels": labels or [],
    }


def _make_commit(
    message: str = "fix: something",
    date: str = "2026-05-15T10:00:00Z",
    author_name: str = "dev1",
) -> dict:
    return {
        "commit": {
            "message": message,
            "author": {"name": author_name, "date": date},
        },
        "html_url": "https://github.com/owner/repo/commit/abc",
    }


@pytest.fixture()
def since() -> datetime:
    return datetime(2026, 5, 10, tzinfo=UTC)


@pytest.fixture()
def until() -> datetime:
    return datetime(2026, 5, 20, tzinfo=UTC)


def _mock_response(
    status_code: int = 200,
    json_data: list | None = None,
    headers: dict | None = None,
) -> httpx.Response:
    """Build a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or []
    resp.headers = headers or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


@pytest.mark.asyncio
async def test_fetch_pull_requests_maps_to_work_items(since: datetime, until: datetime) -> None:
    source = GitHubSource(token="fake", repo="owner/repo")
    pr = _make_pr(labels=[{"name": "enhancement"}])
    source._client.get = AsyncMock(return_value=_mock_response(json_data=[pr]))

    items = await source.fetch_pull_requests(since, until)

    assert len(items) == 1
    item = items[0]
    assert item.title == "Add feature"
    assert item.status == "done"
    assert item.source == "github"
    assert item.assignee == "dev1"
    assert "enhancement" in item.labels
    assert item.completed_at is not None
    await source.close()


@pytest.mark.asyncio
async def test_fetch_pull_requests_filters_by_date(since: datetime, until: datetime) -> None:
    source = GitHubSource(token="fake", repo="owner/repo")
    in_range = _make_pr(title="In range", merged_at="2026-05-15T10:00:00Z")
    too_old = _make_pr(title="Too old", merged_at="2026-05-01T10:00:00Z")
    too_new = _make_pr(title="Too new", merged_at="2026-05-25T10:00:00Z")
    not_merged = _make_pr(title="Not merged", merged_at=None)
    source._client.get = AsyncMock(
        return_value=_mock_response(json_data=[too_new, in_range, too_old, not_merged])
    )

    items = await source.fetch_pull_requests(since, until)

    titles = [i.title for i in items]
    assert "In range" in titles
    assert "Too new" not in titles
    assert "Not merged" not in titles
    await source.close()


@pytest.mark.asyncio
async def test_fetch_pull_requests_truncates_description(since: datetime, until: datetime) -> None:
    source = GitHubSource(token="fake", repo="owner/repo")
    pr = _make_pr()
    pr["body"] = "x" * 500
    source._client.get = AsyncMock(return_value=_mock_response(json_data=[pr]))

    items = await source.fetch_pull_requests(since, until)

    assert len(items[0].description) == 200
    await source.close()


@pytest.mark.asyncio
async def test_fetch_commits(since: datetime, until: datetime) -> None:
    source = GitHubSource(token="fake", repo="owner/repo")
    commit = _make_commit()
    source._client.get = AsyncMock(return_value=_mock_response(json_data=[commit]))

    items = await source.fetch_commits(since, until)

    assert len(items) == 1
    assert items[0].title == "fix: something"
    assert items[0].source == "github"
    await source.close()


@pytest.mark.asyncio
async def test_fetch_pull_requests_auth_error(since: datetime, until: datetime) -> None:
    source = GitHubSource(token="bad", repo="owner/repo")
    source._client.get = AsyncMock(return_value=_mock_response(status_code=401))

    with pytest.raises(SourceAuthError, match="authentication failed"):
        await source.fetch_pull_requests(since, until)
    await source.close()


@pytest.mark.asyncio
async def test_fetch_pull_requests_rate_limit(since: datetime, until: datetime) -> None:
    source = GitHubSource(token="fake", repo="owner/repo")
    source._client.get = AsyncMock(
        return_value=_mock_response(
            status_code=403,
            headers={"x-ratelimit-reset": "1716300000"},
        )
    )

    with pytest.raises(SourceFetchError, match="rate limit"):
        await source.fetch_pull_requests(since, until)
    await source.close()


@pytest.mark.asyncio
async def test_fetch_pull_requests_not_found(since: datetime, until: datetime) -> None:
    source = GitHubSource(token="fake", repo="bad/repo")
    source._client.get = AsyncMock(return_value=_mock_response(status_code=404))

    with pytest.raises(SourceFetchError, match="bad/repo"):
        await source.fetch_pull_requests(since, until)
    await source.close()


@pytest.mark.asyncio
async def test_pagination_follows_link_headers(since: datetime, until: datetime) -> None:
    source = GitHubSource(token="fake", repo="owner/repo")
    pr1 = _make_pr(title="PR 1")
    pr2 = _make_pr(title="PR 2")

    page1 = _mock_response(
        json_data=[pr1],
        headers={"link": '<https://api.github.com/next?page=2>; rel="next"'},
    )
    page2 = _mock_response(json_data=[pr2])
    source._client.get = AsyncMock(side_effect=[page1, page2])

    items = await source.fetch_pull_requests(since, until)

    assert len(items) == 2
    assert source._client.get.call_count == 2
    await source.close()
