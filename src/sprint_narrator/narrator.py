import re

import ollama

from sprint_narrator.aggregator import SprintData, WorkItem
from sprint_narrator.exceptions import NarratorError

SYSTEM_PROMPT = """You are a Technical Program Manager writing a sprint summary.
Write a clear, concise narrative using these exact sections:

## Executive Summary
2-3 sentences on what the team accomplished this sprint.

## Wins
What shipped and why it matters. Use bullet points.

## In Progress
What's actively being worked on.

## Blockers
Anything stuck and what's needed to unblock. If none, say "No blockers this sprint."

## Looking Ahead
Brief outlook for next sprint based on what's in progress.

Rules:
- Keep it under 500 words
- Use specific numbers from the data provided
- Be honest about blockers
- Write for leadership: signal, not noise"""

# Size thresholds in billions of parameters
_SMALL_THRESHOLD = 4
_LARGE_THRESHOLD = 13

_TIER_LIMITS: dict[str, tuple[int, int]] = {
    "small": (20, 0),
    "medium": (40, 50),
    "large": (80, 150),
}

# Known model families and their default sizes (billions)
_KNOWN_SIZES: dict[str, float] = {
    "phi3": 3.8,
    "phi": 2.7,
    "gemma2:2b": 2,
    "gemma:2b": 2,
    "qwen2:1.5b": 1.5,
    "qwen2:0.5b": 0.5,
    "llama3.1:8b": 8,
    "llama3.1:70b": 70,
    "llama3:8b": 8,
    "llama3:70b": 70,
    "mistral": 7,
    "gemma2:9b": 9,
    "gemma2:27b": 27,
    "mixtral": 47,
    "codellama": 7,
}


def check_ollama_health(model: str) -> None:
    """Verify Ollama is running and the requested model is available."""
    try:
        response = ollama.list()
    except ConnectionError as e:
        raise NarratorError("Ollama is not running. Start it with: ollama serve") from e

    available = {m.model for m in response.models}
    # Also match without :latest suffix
    available_base = {m.model.removesuffix(":latest") for m in response.models}

    if model not in available and model not in available_base:
        raise NarratorError(f"Model '{model}' not found. Pull it with: ollama pull {model}")


def _get_model_tier(model: str) -> str:
    """Classify model as small/medium/large based on parameter count."""
    model_lower = model.lower()

    # Check known models first
    for name, size in _KNOWN_SIZES.items():
        if model_lower.startswith(name):
            if size < _SMALL_THRESHOLD:
                return "small"
            if size >= _LARGE_THRESHOLD:
                return "large"
            return "medium"

    # Try to parse size from model string (e.g. "llama3:13b", "model:70b")
    match = re.search(r"(\d+(?:\.\d+)?)b", model_lower)
    if match:
        size = float(match.group(1))
        if size < _SMALL_THRESHOLD:
            return "small"
        if size >= _LARGE_THRESHOLD:
            return "large"
        return "medium"

    return "medium"


def _truncate(text: str, length: int) -> str:
    """Truncate text to length, adding ellipsis if needed."""
    if len(text) <= length:
        return text
    return text[: length - 3] + "..."


def _format_items(items: list[WorkItem], max_items: int, desc_length: int) -> list[str]:
    """Format work items as lines for the prompt context."""
    lines: list[str] = []
    for item in items[:max_items]:
        if desc_length > 0 and item.description:
            desc = _truncate(item.description, desc_length)
            lines.append(f"- {item.title} — {desc}")
        else:
            lines.append(f"- {item.title}")
    return lines


def _format_sprint_context(sprint_data: SprintData, model_tier: str, since: str, until: str) -> str:
    """Build structured text context optimised for local LLMs."""
    max_items, desc_length = _TIER_LIMITS[model_tier]

    sections: list[str] = []

    if since or until:
        period_parts = []
        if since:
            period_parts.append(f"from {since}")
        if until:
            period_parts.append(f"to {until}")
        sections.append(f"SPRINT PERIOD: {' '.join(period_parts)}")
        sections.append("")

    categories = [
        ("SHIPPED", sprint_data.features),
        ("BUG FIXES", sprint_data.bug_fixes),
        ("IN PROGRESS", sprint_data.in_progress),
        ("BLOCKED", sprint_data.blocked),
    ]

    for label, items in categories:
        sections.append(f"{label} ({len(items)}):")
        if items:
            sections.extend(_format_items(items, max_items, desc_length))
        else:
            sections.append("- None")
        sections.append("")

    # Stats line
    total = sum(len(items) for _, items in categories)
    completed = len(sprint_data.features) + len(sprint_data.bug_fixes)
    rate = round(completed / total * 100) if total > 0 else 0
    sections.append(f"STATS: {completed}/{total} items completed ({rate}% completion rate)")

    return "\n".join(sections)


async def generate_narrative(
    sprint_data: SprintData,
    model: str = "llama3.1:8b",
    since: str = "",
    until: str = "",
) -> str:
    """Generate a narrative sprint summary from structured data using Ollama."""
    check_ollama_health(model)

    model_tier = _get_model_tier(model)
    context = _format_sprint_context(sprint_data, model_tier, since, until)

    try:
        client = ollama.AsyncClient()
        response = await client.chat(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Write a sprint summary based on this data:\n\n{context}",
                },
            ],
            options={"temperature": 0.3, "num_ctx": 4096},
        )
    except ollama.ResponseError as e:
        raise NarratorError(f"Ollama request failed: {e}") from e

    return response["message"]["content"]


def generate_fallback_narrative(sprint_data: SprintData) -> str:
    """Template-based summary when Ollama is unavailable."""
    features = len(sprint_data.features)
    bugs = len(sprint_data.bug_fixes)
    in_progress = len(sprint_data.in_progress)
    blocked = len(sprint_data.blocked)
    total = features + bugs + in_progress + blocked
    completed = features + bugs
    rate = round(completed / total * 100) if total > 0 else 0

    parts: list[str] = []
    parts.append(
        f"The team completed {completed} of {total} items this sprint ({rate}% completion rate)."
    )

    details: list[str] = []
    if features:
        details.append(f"{features} feature{'s' if features != 1 else ''} shipped")
    if bugs:
        verb = "were" if bugs != 1 else "was"
        details.append(f"{bugs} bug{'s' if bugs != 1 else ''} {verb} fixed")
    if blocked:
        details.append(
            f"{blocked} item{'s' if blocked != 1 else ''} {'are' if blocked != 1 else 'is'} blocked"
        )
    if details:
        parts.append(" ".join([details[0].capitalize()] + [d for d in details[1:]]) + ".")

    if in_progress:
        parts.append(
            f" {in_progress} item{'s' if in_progress != 1 else ''}"
            f" {'are' if in_progress != 1 else 'is'} still in progress."
        )

    return " ".join(parts)
