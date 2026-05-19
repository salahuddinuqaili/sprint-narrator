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
