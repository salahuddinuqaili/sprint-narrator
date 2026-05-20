# Decisions

## 001 — httpx over requests
httpx supports async natively, which matters when fetching from 3 APIs concurrently. requests would require aiohttp as a separate async library.

## 002 — Direct ollama over LangChain
We need a single chat completion call with a system prompt. LangChain adds chains, memory, and retrieval abstractions we don't use. Direct ollama keeps the dependency tree small.

## 003 — SQLite for archive over external DB
Built into Python's standard library — zero additional dependencies. Sufficient for a local tool archiving weekly summaries. No need for PostgreSQL overhead.

## 004 — Linear GraphQL over REST
Linear's GraphQL API exposes richer filtering (by team, date range, cycle) than their limited REST endpoints. One query replaces multiple REST calls.

## 005 — Modular sources pattern
Each API integration (GitHub, Linear, Jira) is isolated in its own file. This allows independent development, testing, and the ability to add new sources (e.g., Shortcut, Notion) without touching existing code.

## 006 — Manual TOML writing over tomli-w
Config is flat key-value pairs. Writing TOML manually avoids adding a tomli-w dependency for something trivially serialisable.

## 007 — Hatchling build backend
Added `[build-system]` with hatchling so `uv sync` installs the package in editable mode. Required for `sprint_narrator` imports to resolve in tests and the CLI entry point.

## 008 — B008 suppression for cli.py
Typer requires `typer.Option()` calls in function signatures. Suppressed ruff B008 per-file rather than globally.

## 009 — Model-tier prompt adaptation
Local LLMs choke on long contexts. We classify models into small/medium/large tiers and truncate sprint data accordingly (titles-only for <4B, short descriptions for 7-9B, full descriptions for 13B+).

## 010 — Low temperature + explicit num_ctx for Ollama
Temperature 0.3 keeps sprint summaries factual. num_ctx=4096 prevents OOM on 12GB VRAM GPUs that would otherwise auto-allocate larger contexts.
