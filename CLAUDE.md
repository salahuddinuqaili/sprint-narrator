# sprint-narrator

## Tech Stack

- **Language:** Python 3.14
- **Package manager:** uv
- **CLI:** Typer
- **HTTP:** httpx (async)
- **LLM:** ollama Python library
- **Storage:** SQLite (built-in sqlite3)
- **Templating:** Jinja2
- **Linting:** ruff (line-length 100)
- **Testing:** pytest + pytest-asyncio

## Code Conventions

- Strict type hints on all functions
- Sources are modular — each in its own file under `sources/`
- All API calls are async via httpx
- Linear uses GraphQL; GitHub and Jira use REST
- No LangChain — direct ollama library calls
- Entry point: `src/sprint_narrator/cli.py`

## Project Structure

- `cli.py` — Typer commands (run, history, configure)
- `sources/github.py` — GitHub PR/commit fetcher
- `sources/linear.py` — Linear GraphQL client
- `sources/jira.py` — Jira REST client
- `aggregator.py` — Normalize, deduplicate, categorize work items
- `narrator.py` — Ollama narrative generation
- `storage.py` — SQLite archive for past summaries
- `templates/` — Jinja2 templates (markdown + HTML)

## Testing

- All tests in `tests/`
- Mock all external API calls
- `aggregator.py` has unit tests for categorization logic
- Run: `uv run pytest`
