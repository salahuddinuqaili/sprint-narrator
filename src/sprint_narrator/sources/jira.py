from datetime import datetime

import httpx

from sprint_narrator.aggregator import WorkItem


class JiraSource:
    """Fetches issues and sprints from Jira REST API."""

    def __init__(self, base_url: str, email: str, token: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            auth=(email, token),
            headers={"Accept": "application/json"},
            timeout=30.0,
        )

    async def fetch_issues(
        self, since: datetime, until: datetime, project_key: str
    ) -> list[WorkItem]:
        """Fetch sprint issues via JQL query."""
        # TODO: POST /rest/api/3/search with JQL:
        # project = {key} AND updated >= "{since}" AND updated <= "{until}"
        raise NotImplementedError

    async def fetch_sprint(self, board_id: int) -> dict:
        """Fetch active sprint info for a board."""
        # TODO: GET /rest/agile/1.0/board/{boardId}/sprint?state=active
        raise NotImplementedError

    async def close(self) -> None:
        await self._client.aclose()
