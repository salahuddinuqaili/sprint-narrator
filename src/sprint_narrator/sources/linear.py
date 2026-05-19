from datetime import datetime

import httpx

from sprint_narrator.aggregator import WorkItem

# Linear's GraphQL API is more capable than REST for querying issues
ISSUES_QUERY = """
query SprintIssues($teamId: String!, $since: DateTime!, $until: DateTime!) {
  issues(
    filter: {
      team: { id: { eq: $teamId } }
      updatedAt: { gte: $since, lte: $until }
    }
    first: 100
  ) {
    nodes {
      identifier
      title
      description
      state { name }
      assignee { name }
      completedAt
      url
      labels { nodes { name } }
    }
  }
}
"""


class LinearSource:
    """Fetches issues and cycles from Linear's GraphQL API."""

    API_URL = "https://api.linear.app/graphql"

    def __init__(self, token: str) -> None:
        self._client = httpx.AsyncClient(
            headers={"Authorization": token, "Content-Type": "application/json"},
            timeout=30.0,
        )

    async def fetch_issues(
        self, since: datetime, until: datetime, team_id: str
    ) -> list[WorkItem]:
        """Fetch issues updated in the date range for a team."""
        # TODO: Execute ISSUES_QUERY, map response to WorkItem list
        raise NotImplementedError

    async def fetch_cycles(self, team_id: str) -> list[dict]:
        """Fetch current and recent cycles for a team."""
        # TODO: Query cycles via GraphQL
        raise NotImplementedError

    async def close(self) -> None:
        await self._client.aclose()
