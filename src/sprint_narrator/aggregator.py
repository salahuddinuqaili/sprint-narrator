from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class WorkItem:
    title: str
    description: str
    status: str
    assignee: str
    source: str  # "github", "linear", or "jira"
    url: str
    completed_at: datetime | None = None
    labels: list[str] = field(default_factory=list)


@dataclass
class SprintData:
    features: list[WorkItem]
    bug_fixes: list[WorkItem]
    in_progress: list[WorkItem]
    blocked: list[WorkItem]
    other: list[WorkItem]
    stats: dict


def aggregate(items: list[WorkItem]) -> SprintData:
    """Normalize, deduplicate, and categorize work items from all sources."""
    # Deduplicate by title similarity
    seen_titles: set[str] = set()
    unique: list[WorkItem] = []
    for item in items:
        normalized = item.title.lower().strip()
        if normalized not in seen_titles:
            seen_titles.add(normalized)
            unique.append(item)

    features: list[WorkItem] = []
    bug_fixes: list[WorkItem] = []
    in_progress: list[WorkItem] = []
    blocked: list[WorkItem] = []
    other: list[WorkItem] = []

    for item in unique:
        labels_lower = [l.lower() for l in item.labels]
        status_lower = item.status.lower()

        if "blocked" in status_lower or "blocked" in labels_lower:
            blocked.append(item)
        elif status_lower in ("in progress", "in_progress", "started"):
            in_progress.append(item)
        elif "bug" in labels_lower or "fix" in labels_lower:
            bug_fixes.append(item)
        elif "feature" in labels_lower or "enhancement" in labels_lower:
            features.append(item)
        else:
            # Default completed items to features, rest to other
            if item.completed_at:
                features.append(item)
            else:
                other.append(item)

    completed = [i for i in unique if i.completed_at]
    assignees = {i.assignee for i in unique if i.assignee}

    return SprintData(
        features=features,
        bug_fixes=bug_fixes,
        in_progress=in_progress,
        blocked=blocked,
        other=other,
        stats={
            "total": len(unique),
            "completed": len(completed),
            "completion_rate": f"{len(completed) / max(len(unique), 1) * 100:.0f}%",
            "contributors": sorted(assignees),
        },
    )
