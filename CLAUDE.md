# sprint-narrator

## Tech Stack

- **Python** ≥3.13 (uv as package manager)
- **CLI:** Typer + Rich
- **HTTP:** httpx (async)
- **LLM:** ollama library — no LangChain
- **Storage:** SQLite (stdlib sqlite3)
- **Templating:** Jinja2
- **Lint:** ruff (line-length 100, target py313, rules: E/F/I/UP/B/SIM)
- **Test:** pytest + pytest-asyncio

## Commands

```bash
uv run sprint-narrator          # run the CLI
uv run pytest                   # tests
uv run ruff check src tests     # lint
uv run ruff format src tests    # format
```

## Code Conventions

- Strict type hints on all functions
- All API calls are async via httpx
- Linear uses GraphQL; GitHub and Jira use REST
- Sources are modular — each integration in its own file under `sources/`
- Templates live in `src/sprint_narrator/templates/` (`.md.j2` and `.html.j2`)
- Entry point: `src/sprint_narrator/cli.py`

## Testing

- All tests in `tests/`, mock all external API calls
- `test_aggregator.py` — categorization logic unit tests
- `test_cli.py` — CLI integration tests
