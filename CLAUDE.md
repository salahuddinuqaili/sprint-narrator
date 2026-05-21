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
- `test_cli.py` — CLI integration tests (end-to-end, dry-run, fallback, concurrent sources)
- `test_config.py` — config load/save, env var overrides, token masking
- `test_github.py` — GitHub REST source (async, uses `AsyncMock`)
- `test_linear.py` — Linear GraphQL source (cursor pagination, state mapping)
- `test_jira.py` — Jira REST source (JQL, ADF extraction, agile endpoints)
- `test_narrator.py` — Ollama health checks, model tiers, narrative generation
- `test_render.py` — Jinja2 template rendering (md + html)

## Key Patterns

- CLI uses `asyncio.run()` to bridge sync Typer commands to async pipeline
- Multiple sources fetch concurrently via `asyncio.gather(return_exceptions=True)`
- Narrator catches `NarratorError` internally and falls back to template narrative
- Mock sources at `sprint_narrator.cli._fetch_github` etc; mock narrator at `sprint_narrator.narrator.generate_narrative`
- ruff B008 suppressed in `cli.py` only (Typer requires `typer.Option()` in signatures)
