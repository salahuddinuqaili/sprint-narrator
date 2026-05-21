# sprint-narrator

![CI](https://github.com/salahuddinuqaili/sprint-narrator/actions/workflows/ci.yml/badge.svg)

AI-powered sprint summary generator that pulls from GitHub, Linear, and Jira to create narrative reports using local LLMs via Ollama.

> Turn ticket data into leadership-ready sprint summaries — fully local, no API keys to OpenAI required.

## Why

Sprint reviews shouldn't start with someone scrolling through Jira for 10 minutes. sprint-narrator pulls completed work from your tools, categorises it, and generates a narrative summary using a local LLM. The output is a concise, leadership-ready report — not a ticket dump.

## Features

- **Multi-source aggregation** — GitHub (PRs + commits), Linear (GraphQL), and Jira (REST + Agile endpoints)
- **Local LLM narratives** — Ollama-powered generation with model-tier prompt adaptation (small/medium/large)
- **Smart categorisation** — automatically sorts work into Shipped, Bug Fixes, In Progress, and Blocked
- **Fallback mode** — template-based summaries when Ollama is unavailable
- **Dual output formats** — Markdown and styled HTML
- **Local archive** — SQLite history of past summaries
- **12GB VRAM optimised** — explicit context window and temperature tuning for consumer GPUs

## Try It

```bash
uv sync                    # install dependencies
sprint-narrator demo       # see sample output — no API keys needed
```

## Quick Start

```bash
# Install with uv
uv sync

# Configure at least one source
sprint-narrator configure --github-token ghp_... --github-repo owner/repo

# Generate a sprint summary (defaults to last 7 days)
sprint-narrator run --source github

# Use multiple sources
sprint-narrator run -s github -s linear -s jira

# Output as HTML
sprint-narrator run -s github --format html -o summary.html

# Save to local archive
sprint-narrator run -s github --save

# View past summaries
sprint-narrator history
```

## Configuration

Tokens can be set via CLI or environment variables:

```bash
# CLI
sprint-narrator configure --github-token <token> --github-repo owner/repo
sprint-narrator configure --linear-token <token> --linear-team-id <id>
sprint-narrator configure --jira-url https://org.atlassian.net --jira-email you@org.com \
  --jira-token <token> --jira-project-key PROJ

# Environment variables
export SPRINT_NARRATOR_GITHUB_TOKEN=ghp_...
export SPRINT_NARRATOR_GITHUB_REPOS=owner/repo1,owner/repo2
export SPRINT_NARRATOR_LINEAR_TOKEN=lin_...
export SPRINT_NARRATOR_DEFAULT_MODEL=mistral

# View current config (tokens masked)
sprint-narrator configure --show
```

Config is stored in `~/.config/sprint-narrator/config.toml`.

## LLM Configuration

sprint-narrator uses Ollama for local inference. Any model works — the prompt adapts to model size:

| Tier | Models | Context sent |
|------|--------|-------------|
| Small (<4B) | phi3, gemma2:2b, qwen2:1.5b | Titles only, max 20 items |
| Medium (7-9B) | llama3.1:8b, mistral, gemma2:9b | Titles + short descriptions, max 40 items |
| Large (13B+) | llama3.1:70b, mixtral | Full descriptions, max 80 items |

```bash
# Use a specific model
sprint-narrator run -s github --model mistral

# Set a default model
sprint-narrator configure --default-model mistral
```

If Ollama is not running or the model isn't pulled, sprint-narrator falls back to a template-based summary automatically.

## Architecture

```
CLI (Typer + Rich)
 ├── Sources (async httpx)
 │   ├── GitHub  — REST API, PR + commit fetching, Link-header pagination
 │   ├── Linear  — GraphQL, cursor-based pagination
 │   └── Jira    — REST + Agile APIs, JQL search, ADF text extraction
 ├── Aggregator  — dedup, categorise, compute stats
 ├── Narrator    — Ollama async chat with tier-adapted prompts
 ├── Renderer    — Jinja2 templates (Markdown / HTML)
 └── Storage     — SQLite archive
```

## Tech Stack

- **Python** 3.13+ with strict type hints
- **CLI:** Typer + Rich
- **HTTP:** httpx (async)
- **LLM:** ollama (direct, no LangChain)
- **Storage:** SQLite (stdlib)
- **Templates:** Jinja2
- **Lint:** ruff
- **Test:** pytest + pytest-asyncio

## Development

```bash
uv sync                          # install dependencies
uv run pytest -v                 # run tests (78 passing)
uv run ruff check src tests      # lint
uv run ruff format src tests     # format
```

## License

MIT
