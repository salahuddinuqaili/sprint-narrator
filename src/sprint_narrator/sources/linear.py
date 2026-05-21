from __future__ import annotations

from datetime import datetime

import httpx

from sprint_narrator.aggregator import WorkItem
from sprint_narrator.exceptions import SourceAuthError, SourceFetchError

ISSUES_QUERY = """
query SprintIssues($teamId: String!, $since: DateTime!, $until: DateTime!, $after: String) {
  issues(
    filter: {
      team: { id: { eq: $teamId } }
      updatedAt: { gte: $since, lte: $until }
    }
    first: 100
    after: $after
    orderBy: updatedAt
  ) {
    nodes {
      identifier
      title
      description
      state { name }
      assignee { displayName }
      completedAt
      url
      labels { nodes { name } }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

CYCLES_QUERY = """
query TeamCycles($teamId: String!) {
  team(id: $teamId) {
    cycles(
      first: 5
      orderBy: createdAt
    ) {
      nodes {
        name
        number
        startsAt
        endsAt
        progress
        completedScopeCount
        scopeCount
      }
    }
  }
}
"""

# Map Linear state names to our internal status
_STATE_MAP: dict[str, str] = {
    "done": "done",
    "completed": "done",
    "in progress": "in_progress",
    "started": "in_progress",
    "blocked": "blocked",
}


class LinearSource:
    """Fetches issues and cycles from Linear's GraphQL API."""

    API_URL = "https://api.linear.app/graphql"
    MAX_PAGES = 5

    def __init__(self, token: str, team_id: str) -> None:
        self._team_id = team_id
        self._client = httpx.AsyncClient(
            headers={"Authorization": token, "Content-Type": "application/json"},
            timeout=30.0,
        )

    async def _execute(self, query: str, variables: dict) -> dict:
        """Execute a GraphQL query and return the data payload."""
        response = await self._client.post(
            self.API_URL,
            json={"query": query, "variables": variables},
        )

        if response.status_code == 401:
            raise SourceAuthError("Linear authentication failed. Check your API key is valid.")
        if response.status_code >= 400:
            raise SourceFetchError(f"Linear API returned HTTP {response.status_code}.")

        body = response.json()

        if "errors" in body:
            msg = body["errors"][0].get("message", "Unknown GraphQL error")
            raise SourceFetchError(f"Linear GraphQL error: {msg}")

        return body.get("data", {})

    async def fetch_issues(self, since: datetime, until: datetime) -> list[WorkItem]:
        """Fetch issues updated in the date range for the configured team."""
        variables: dict = {
            "teamId": self._team_id,
            "since": since.isoformat(),
            "until": until.isoformat(),
            "after": None,
        }

        items: list[WorkItem] = []

        for _ in range(self.MAX_PAGES):
            data = await self._execute(ISSUES_QUERY, variables)
            issues_data = data.get("issues", {})
            nodes = issues_data.get("nodes", [])

            for node in nodes:
                state_name = (node.get("state") or {}).get("name", "")
                status = _STATE_MAP.get(state_name.lower(), "other")

                assignee_data = node.get("assignee") or {}
                assignee = assignee_data.get("displayName", "unassigned")

                label_nodes = (node.get("labels") or {}).get("nodes", [])
                labels = [lbl["name"] for lbl in label_nodes]

                description = node.get("description") or ""

                completed_at = None
                if node.get("completedAt"):
                    completed_at = datetime.fromisoformat(
                        node["completedAt"].replace("Z", "+00:00")
                    )

                items.append(
                    WorkItem(
                        title=node["title"],
                        description=description[:200],
                        status=status,
                        assignee=assignee,
                        source="linear",
                        url=node.get("url", ""),
                        completed_at=completed_at,
                        labels=labels,
                    )
                )

            page_info = issues_data.get("pageInfo", {})
            if not page_info.get("hasNextPage", False):
                break
            variables["after"] = page_info["endCursor"]

        return items

    async def fetch_cycles(self, since: datetime, until: datetime) -> list[dict]:
        """Fetch current and recent cycles for the team."""
        data = await self._execute(CYCLES_QUERY, {"teamId": self._team_id})
        team_data = data.get("team") or {}
        cycle_nodes = (team_data.get("cycles") or {}).get("nodes", [])

        cycles: list[dict] = []
        for node in cycle_nodes:
            starts_at = node.get("startsAt", "")
            ends_at = node.get("endsAt", "")

            # Filter to cycles overlapping the requested range
            if ends_at and ends_at < since.isoformat():
                continue
            if starts_at and starts_at > until.isoformat():
                continue

            cycles.append(
                {
                    "name": node.get("name") or f"Cycle {node.get('number', '?')}",
                    "starts_at": starts_at,
                    "ends_at": ends_at,
                    "progress": node.get("progress", 0),
                    "completed_scope": node.get("completedScopeCount", 0),
                    "total_scope": node.get("scopeCount", 0),
                }
            )

        return cycles

    async def close(self) -> None:
        await self._client.aclose()
