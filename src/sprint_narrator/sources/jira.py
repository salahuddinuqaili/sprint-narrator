from __future__ import annotations

from datetime import datetime

import httpx

from sprint_narrator.aggregator import WorkItem
from sprint_narrator.exceptions import SourceAuthError, SourceFetchError

_STATE_MAP: dict[str, str] = {
    "done": "done",
    "closed": "done",
    "resolved": "done",
    "in progress": "in_progress",
    "blocked": "blocked",
}

_SEARCH_FIELDS = [
    "summary",
    "description",
    "status",
    "assignee",
    "labels",
    "resolutiondate",
]


class JiraSource:
    """Fetches issues and sprints from Jira REST API."""

    MAX_PAGES = 5
    PAGE_SIZE = 100

    def __init__(
        self, url: str, email: str, token: str, project_key: str
    ) -> None:
        self._base_url = url.rstrip("/")
        self._project_key = project_key
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            auth=(email, token),
            headers={"Accept": "application/json"},
            timeout=30.0,
        )

    def _check_response(self, response: httpx.Response) -> None:
        """Raise typed errors for common Jira API failures."""
        if response.status_code in (401, 403):
            raise SourceAuthError(
                "Jira authentication failed. Check your email and API token."
            )
        if response.status_code >= 400:
            raise SourceFetchError(
                f"Jira API returned HTTP {response.status_code}."
            )

    async def fetch_issues(
        self, since: datetime, until: datetime
    ) -> list[WorkItem]:
        """Fetch issues via JQL query with offset-based pagination."""
        since_str = since.strftime("%Y-%m-%d")
        until_str = until.strftime("%Y-%m-%d")

        jql = (
            f'project = "{self._project_key}"'
            f' AND updated >= "{since_str}"'
            f' AND updated <= "{until_str}"'
            f" ORDER BY updated DESC"
        )

        items: list[WorkItem] = []
        start_at = 0

        for _ in range(self.MAX_PAGES):
            response = await self._client.get(
                "/rest/api/3/search",
                params={
                    "jql": jql,
                    "fields": ",".join(_SEARCH_FIELDS),
                    "maxResults": self.PAGE_SIZE,
                    "startAt": start_at,
                },
            )
            self._check_response(response)

            body = response.json()
            issues = body.get("issues", [])

            for issue in issues:
                fields = issue.get("fields", {})

                status_name = (fields.get("status") or {}).get("name", "")
                status = _STATE_MAP.get(status_name.lower(), "other")

                assignee_data = fields.get("assignee")
                assignee = (
                    assignee_data.get("displayName", "unassigned")
                    if assignee_data
                    else "unassigned"
                )

                description_body = fields.get("description")
                description = ""
                if isinstance(description_body, str):
                    description = description_body[:200]
                elif isinstance(description_body, dict):
                    # ADF format — extract text from content nodes
                    description = _extract_adf_text(description_body)[:200]

                labels = fields.get("labels") or []

                completed_at = None
                resolution_date = fields.get("resolutiondate")
                if resolution_date:
                    completed_at = datetime.fromisoformat(
                        resolution_date.replace("Z", "+00:00")
                    )

                issue_key = issue.get("key", "")
                browse_url = f"{self._base_url}/browse/{issue_key}"

                items.append(WorkItem(
                    title=fields.get("summary", ""),
                    description=description,
                    status=status,
                    assignee=assignee,
                    source="jira",
                    url=browse_url,
                    completed_at=completed_at,
                    labels=labels,
                ))

            total = body.get("total", 0)
            start_at += len(issues)
            if start_at >= total or not issues:
                break

        return items

    async def fetch_sprint(
        self, since: datetime, until: datetime
    ) -> list[dict]:
        """Fetch active/recent sprints via Jira Agile endpoints.

        Returns empty list if agile endpoints are unavailable.
        """
        try:
            # Discover the board for this project
            board_resp = await self._client.get(
                "/rest/agile/1.0/board",
                params={"projectKeyOrId": self._project_key, "maxResults": 1},
            )
            if board_resp.status_code >= 400:
                return []

            boards = board_resp.json().get("values", [])
            if not boards:
                return []

            board_id = boards[0]["id"]

            # Fetch sprints for the board
            sprint_resp = await self._client.get(
                f"/rest/agile/1.0/board/{board_id}/sprint",
                params={"maxResults": 10},
            )
            if sprint_resp.status_code >= 400:
                return []

            sprints: list[dict] = []
            for s in sprint_resp.json().get("values", []):
                start_date = s.get("startDate", "")
                end_date = s.get("endDate", "")

                # Filter to sprints overlapping the requested range
                if end_date and end_date < since.isoformat():
                    continue
                if start_date and start_date > until.isoformat():
                    continue

                sprints.append({
                    "name": s.get("name", ""),
                    "state": s.get("state", ""),
                    "start_date": start_date,
                    "end_date": end_date,
                    "goal": s.get("goal", ""),
                })

            return sprints

        except httpx.HTTPError:
            return []

    async def close(self) -> None:
        await self._client.aclose()


def _extract_adf_text(doc: dict) -> str:
    """Extract plain text from Jira's Atlassian Document Format."""
    parts: list[str] = []
    for block in doc.get("content", []):
        for inline in block.get("content", []):
            if inline.get("type") == "text":
                parts.append(inline.get("text", ""))
    return " ".join(parts)
