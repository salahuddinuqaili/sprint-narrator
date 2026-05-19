import ollama

from sprint_narrator.aggregator import SprintData

SYSTEM_PROMPT = """You are a Technical Program Manager writing a sprint summary for your team.
Write in a clear, concise narrative voice. Structure your summary as:

1. **Executive Summary** — 2-3 sentences on what the team accomplished this sprint
2. **Wins** — what shipped and why it matters
3. **In Progress** — what's actively being worked on
4. **Blockers** — anything stuck and what's needed to unblock
5. **Looking Ahead** — brief outlook for next sprint

Keep it under 500 words. Use specific numbers and names. Be honest about blockers.
Write for a leadership audience who wants the signal, not the noise."""


async def generate_narrative(sprint_data: SprintData, model: str = "llama3.1:8b") -> str:
    """Generate a narrative sprint summary from structured data."""
    # TODO: Format SprintData into a prompt context, call ollama.chat()
    raise NotImplementedError
