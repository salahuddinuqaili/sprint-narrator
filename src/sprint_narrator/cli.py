import asyncio
from datetime import datetime, timedelta
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from sprint_narrator import __version__
from sprint_narrator.config import display_config, get_token_for_source, load_config, save_config
from sprint_narrator.exceptions import (
    NarratorError,
    SourceAuthError,
    SourceFetchError,
    SprintNarratorError,
)

app = typer.Typer(
    name="sprint-narrator",
    help="Generate narrative sprint summaries from Linear, Jira, and GitHub.",
)
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"sprint-narrator v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True,
    ),
) -> None:
    pass


async def _fetch_github(
    token: str, repos: list[str], since: datetime, until: datetime
) -> list:
    """Fetch work items from all configured GitHub repos."""
    from sprint_narrator.sources.github import GitHubSource

    items: list = []
    for repo in repos:
        source = GitHubSource(token=token, repo=repo)
        try:
            prs = await source.fetch_pull_requests(since, until)
            commits = await source.fetch_commits(since, until)
            items.extend(prs)
            items.extend(commits)
        finally:
            await source.close()
    return items


async def _fetch_linear(
    token: str, team_id: str, since: datetime, until: datetime
) -> list:
    """Fetch work items from Linear for a team."""
    from sprint_narrator.sources.linear import LinearSource

    source = LinearSource(token=token, team_id=team_id)
    try:
        return await source.fetch_issues(since, until)
    finally:
        await source.close()


async def _fetch_jira(
    url: str, email: str, token: str, project_key: str,
    since: datetime, until: datetime,
) -> list:
    """Fetch work items from Jira for a project."""
    from sprint_narrator.sources.jira import JiraSource

    source = JiraSource(url=url, email=email, token=token, project_key=project_key)
    try:
        return await source.fetch_issues(since, until)
    finally:
        await source.close()


def _print_dry_run_stats(sprint_data: object) -> None:
    """Display aggregated sprint stats as a table."""
    table = Table(title="Sprint Data (dry run)")
    table.add_column("Category", style="bold")
    table.add_column("Count", justify="right")
    table.add_row("Features", str(len(sprint_data.features)))
    table.add_row("Bug Fixes", str(len(sprint_data.bug_fixes)))
    table.add_row("In Progress", str(len(sprint_data.in_progress)))
    table.add_row("Blocked", str(len(sprint_data.blocked)))
    table.add_row("Other", str(len(sprint_data.other)))
    table.add_row("Contributors", ", ".join(sprint_data.stats.get("contributors", [])))
    console.print(table)


async def _run_pipeline(
    sources: list[str],
    since_str: str,
    until_str: str,
    model: str,
    fmt: str,
    output: Path | None,
    save: bool,
    dry_run: bool = False,
) -> None:
    """Async pipeline: fetch → aggregate → narrate → render."""
    from sprint_narrator.aggregator import WorkItem, aggregate
    from sprint_narrator.narrator import generate_fallback_narrative, generate_narrative
    from sprint_narrator.render import render_output

    config = load_config()

    since_dt = datetime.fromisoformat(since_str)
    until_dt = datetime.fromisoformat(until_str)

    # Validate configs and build fetch coroutines
    fetch_coros: dict[str, object] = {}
    for src in sources:
        token = get_token_for_source(src, config)

        if src == "github":
            if not config.github_repos:
                console.print(
                    "[red]No GitHub repos configured.[/red]\n"
                    "  Set via: sprint-narrator configure --github-repo owner/repo"
                )
                raise typer.Exit(1)
            fetch_coros[src] = _fetch_github(
                token, config.github_repos, since_dt, until_dt
            )
        elif src == "linear":
            if not config.linear_team_id:
                console.print(
                    "[red]No Linear team ID configured.[/red]\n"
                    "  Set via: sprint-narrator configure --linear-team-id <id>"
                )
                raise typer.Exit(1)
            fetch_coros[src] = _fetch_linear(
                token, config.linear_team_id, since_dt, until_dt
            )
        elif src == "jira":
            missing = []
            if not config.jira_url:
                missing.append("--jira-url")
            if not config.jira_email:
                missing.append("--jira-email")
            if not config.jira_project_key:
                missing.append("--jira-project-key")
            if missing:
                console.print(
                    f"[red]Jira config incomplete. Missing: {', '.join(missing)}[/red]\n"
                    "  Set via: sprint-narrator configure <option> <value>"
                )
                raise typer.Exit(1)
            fetch_coros[src] = _fetch_jira(
                url=config.jira_url,
                email=config.jira_email,
                token=token,
                project_key=config.jira_project_key,
                since=since_dt,
                until=until_dt,
            )
        else:
            console.print(f"  [red]Unknown source: {src}[/red]")

    if not fetch_coros:
        console.print("[yellow]No valid sources to fetch from.[/yellow]")
        raise typer.Exit(0)

    # Fetch from all sources concurrently
    source_names = list(fetch_coros.keys())
    with console.status("[bold]Fetching from sources..."):
        results = await asyncio.gather(
            *fetch_coros.values(), return_exceptions=True
        )

    # Process results — collect items from successes, report failures
    all_items: list[WorkItem] = []
    for src, result in zip(source_names, results, strict=True):
        if isinstance(result, SourceAuthError):
            console.print(
                f"  [red]{src.title()}:[/red] authentication failed. "
                f"Run: sprint-narrator configure --{src}-token <token>"
            )
        elif isinstance(result, SourceFetchError):
            console.print(
                f"  [yellow]{src.title()}:[/yellow] fetch error: {result}"
            )
        elif isinstance(result, Exception):
            console.print(
                f"  [red]{src.title()}:[/red] unexpected error: {result}"
            )
        else:
            all_items.extend(result)
            count = len(result)
            console.print(f"  [green]{src.title()}:[/green] fetched {count} items")

    if not all_items:
        console.print("[yellow]No work items found for this period.[/yellow]")
        raise typer.Exit(0)

    sprint_data = aggregate(all_items)
    console.print(
        f"  Aggregated: {sprint_data.stats['total']} items,"
        f" {sprint_data.stats['completed']} completed"
    )

    # Dry run — show stats and exit
    if dry_run:
        _print_dry_run_stats(sprint_data)
        return

    # Generate narrative — fallback if Ollama is unavailable
    try:
        with console.status(
            f"[bold]Generating narrative with {model}..."
        ):
            narrative = await generate_narrative(
                sprint_data, model=model, since=since_str, until=until_str
            )
    except NarratorError as e:
        console.print(f"  [yellow]LLM unavailable: {e}[/yellow]")
        console.print("  [yellow]Using fallback narrative.[/yellow]")
        narrative = generate_fallback_narrative(sprint_data)

    rendered = render_output(
        narrative=narrative,
        sprint_data=sprint_data,
        fmt=fmt,
        since=since_str,
        until=until_str,
        sources=sources,
    )

    if output:
        output.write_text(rendered, encoding="utf-8")
        console.print(f"  [green]Written to {output}[/green]")
    else:
        console.print()
        if fmt == "md":
            console.print(Markdown(rendered))
        else:
            console.print(rendered)

    if save:
        from sprint_narrator.storage import save_summary

        date_range = f"{since_str} to {until_str}"
        save_summary(date_range=date_range, sources=sources, narrative=narrative)
        console.print("  [green]Summary saved to archive.[/green]")


@app.command()
def run(
    source: list[str] = typer.Option(
        ..., "--source", "-s", help="Data source: github, linear, jira."
    ),
    since: str | None = typer.Option(
        None, help="Start date (YYYY-MM-DD). Defaults to 7 days ago."
    ),
    until: str | None = typer.Option(
        None, help="End date (YYYY-MM-DD). Defaults to today."
    ),
    model: str = typer.Option(
        "llama3.1:8b", help="Ollama model for narrative generation."
    ),
    output: Path | None = typer.Option(None, "-o", help="Output file path."),
    format: str = typer.Option("md", help="Output format: md or html."),
    save: bool = typer.Option(
        False, help="Save summary to local archive."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Fetch and aggregate only, skip narrative."
    ),
) -> None:
    """Generate a sprint summary from configured sources."""
    start = since or (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    end = until or datetime.now().strftime("%Y-%m-%d")

    console.print(
        f"[bold]Generating sprint summary ({start} to {end})...[/bold]"
    )
    console.print(f"Sources: {', '.join(source)}")

    try:
        asyncio.run(_run_pipeline(
            sources=source,
            since_str=start,
            until_str=end,
            model=model,
            fmt=format,
            output=output,
            save=save,
            dry_run=dry_run,
        ))
    except SprintNarratorError as e:
        console.print(Panel(
            f"{e}",
            title=type(e).__name__,
            border_style="red",
        ))
        raise typer.Exit(1) from None


@app.command()
def history(
    limit: int = typer.Option(10, help="Number of past summaries to show."),
) -> None:
    """Show past sprint summaries from the archive."""
    from sprint_narrator.storage import get_history

    summaries = get_history(limit)
    if not summaries:
        console.print("[yellow]No past summaries found.[/yellow]")
        return

    table = Table(title="Sprint Summary Archive")
    table.add_column("Date Range", style="bold")
    table.add_column("Sources")
    table.add_column("Words", justify="right")
    table.add_column("Saved At")

    for s in summaries:
        word_count = str(len(s["narrative"].split()))
        table.add_row(s["date_range"], s["sources"], word_count, s["created_at"])

    console.print(table)


@app.command()
def configure(
    github_token: str | None = typer.Option(
        None, help="GitHub personal access token."
    ),
    github_repo: list[str] | None = typer.Option(
        None, help="GitHub repos (owner/repo)."
    ),
    linear_token: str | None = typer.Option(None, help="Linear API key."),
    linear_team_id: str | None = typer.Option(None, help="Linear team ID."),
    jira_url: str | None = typer.Option(None, help="Jira instance URL."),
    jira_email: str | None = typer.Option(
        None, help="Jira account email."
    ),
    jira_token: str | None = typer.Option(None, help="Jira API token."),
    jira_project_key: str | None = typer.Option(
        None, help="Jira project key."
    ),
    default_model: str | None = typer.Option(
        None, help="Default Ollama model."
    ),
    show: bool = typer.Option(
        False, help="Show current config (tokens masked)."
    ),
) -> None:
    """Set API tokens and defaults."""
    config = load_config()

    if show:
        table = Table(title="sprint-narrator config")
        table.add_column("Setting", style="bold")
        table.add_column("Value")
        for key, val in display_config(config).items():
            table.add_row(key, val)
        console.print(table)
        return

    # Merge non-None arguments into existing config
    if github_token is not None:
        config.github_token = github_token
    if github_repo is not None:
        config.github_repos = github_repo
    if linear_token is not None:
        config.linear_token = linear_token
    if linear_team_id is not None:
        config.linear_team_id = linear_team_id
    if jira_url is not None:
        config.jira_url = jira_url
    if jira_email is not None:
        config.jira_email = jira_email
    if jira_token is not None:
        config.jira_token = jira_token
    if jira_project_key is not None:
        config.jira_project_key = jira_project_key
    if default_model is not None:
        config.default_model = default_model

    save_config(config)
    console.print("[green]Config saved.[/green]")
