from __future__ import annotations

import re
from datetime import datetime

import httpx

from sprint_narrator.aggregator import WorkItem
from sprint_narrator.exceptions import SourceAuthError, SourceFetchError


class GitHubSource:
    """Fetches PRs and commits from GitHub REST API."""

    BASE_URL = "https://api.github.com"
    MAX_PAGES = 5

    def __init__(self, token: str, repo: str) -> None:
        self._repo = repo
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=30.0,
        )

    async def fetch_pull_requests(self, since: datetime, until: datetime) -> list[WorkItem]:
        """Fetch merged PRs in the date range."""
        params: dict[str, str | int] = {
            "state": "closed",
            "sort": "updated",
            "direction": "desc",
            "per_page": 100,
        }

        items: list[WorkItem] = []
        pages = await self._paginate(f"/repos/{self._repo}/pulls", params)

        for pr in pages:
            merged_at = pr.get("merged_at")
            if not merged_at:
                continue

            merged_dt = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
            # GitHub returns newest first — stop early if we've passed the window
            if merged_dt < since:
                break
            if merged_dt > until:
                continue

            body = pr.get("body") or ""
            labels = [lbl["name"] for lbl in pr.get("labels", [])]
            user = pr.get("user", {})

            items.append(
                WorkItem(
                    title=pr["title"],
                    description=body[:200],
                    status="done",
                    assignee=user.get("login", "unknown"),
                    source="github",
                    url=pr["html_url"],
                    completed_at=merged_dt,
                    labels=labels,
                )
            )

        return items

    async def fetch_commits(self, since: datetime, until: datetime) -> list[WorkItem]:
        """Fetch commits in the date range."""
        params: dict[str, str | int] = {
            "since": since.isoformat(),
            "until": until.isoformat(),
            "per_page": 100,
        }

        items: list[WorkItem] = []
        pages = await self._paginate(f"/repos/{self._repo}/commits", params)

        for commit in pages:
            commit_data = commit.get("commit", {})
            author_info = commit_data.get("author", {})
            date_str = author_info.get("date", "")
            message = commit_data.get("message", "")

            committed_at = None
            if date_str:
                committed_at = datetime.fromisoformat(date_str.replace("Z", "+00:00"))

            items.append(
                WorkItem(
                    title=message.split("\n", 1)[0],
                    description=message[:200],
                    status="done",
                    assignee=author_info.get("name", "unknown"),
                    source="github",
                    url=commit.get("html_url", ""),
                    completed_at=committed_at,
                )
            )

        return items

    async def _paginate(self, url: str, params: dict[str, str | int]) -> list[dict]:
        """Fetch pages following Link headers, up to MAX_PAGES."""
        all_items: list[dict] = []
        next_url: str | None = url

        for _ in range(self.MAX_PAGES):
            if next_url is None:
                break

            response = await self._client.get(next_url, params=params)
            self._check_response(response)

            all_items.extend(response.json())
            # Only use params on the first request; Link URLs include them
            params = {}
            next_url = self._parse_next_link(response.headers.get("link", ""))

        return all_items

    def _check_response(self, response: httpx.Response) -> None:
        """Raise typed errors for common GitHub API failures."""
        if response.status_code == 401:
            raise SourceAuthError("GitHub authentication failed. Check your token is valid.")
        if response.status_code == 403:
            reset = response.headers.get("x-ratelimit-reset", "")
            msg = "GitHub API rate limit exceeded."
            if reset:
                msg += f" Resets at timestamp {reset}."
            raise SourceFetchError(msg)
        if response.status_code == 404:
            raise SourceFetchError(
                f"GitHub repo '{self._repo}' not found. Check the owner/repo format."
            )
        response.raise_for_status()

    @staticmethod
    def _parse_next_link(link_header: str) -> str | None:
        """Extract the 'next' URL from a GitHub Link header."""
        if not link_header:
            return None
        match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
        return match.group(1) if match else None

    async def close(self) -> None:
        await self._client.aclose()
