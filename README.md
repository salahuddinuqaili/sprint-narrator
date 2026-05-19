# sprint-narrator

AI-powered sprint summary generator that pulls from Linear, Jira, and GitHub to create narrative reports.

## Features

- Multi-source data aggregation (Linear, Jira, GitHub)
- LLM-powered narrative summaries via Ollama
- Automatic categorization: shipped, bug fixes, in progress, blocked
- SQLite archive for historical summaries
- Markdown and HTML output formats

## Quick Start

```bash
# Install
uv sync

# Configure API tokens
sprint-narrator configure --github-token ghp_... --linear-token lin_...

# Generate a sprint summary (last 7 days)
sprint-narrator run --source github --source linear

# View past summaries
sprint-narrator history
```

## Example Output

```
# Sprint Summary
**2026-05-13 to 2026-05-20** | Sources: github, linear

The team shipped 8 features this sprint, led by the new auth flow...
```

## Development

```bash
uv sync                  # Install dependencies
uv run pytest            # Run tests
uv run ruff check src/   # Lint
```
