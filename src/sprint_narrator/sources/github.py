from datetime import datetime

import httpx

from sprint_narrator.aggregator import WorkItem


class GitHubSource:
    """Fetches PRs and commits from GitHub REST API."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str, repo: str) -> None:
        self._repo = repo
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            timeout=30.0,
        )

    async def fetch_pull_requests(
        self, since: datetime, until: datetime
    ) -> list[WorkItem]:
        """Fetch merged PRs in the date range."""
        # TODO: GET /repos/{repo}/pulls?state=closed, filter by merged_at
        raise NotImplementedError

    async def fetch_commits(
        self, since: datetime, until: datetime
    ) -> list[WorkItem]:
        """Fetch commits in the date range."""
        # TODO: GET /repos/{repo}/commits?since=...&until=...
        raise NotImplementedError

    async def close(self) -> None:
        await self._client.aclose()
