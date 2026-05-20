from datetime import datetime, timedelta
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from sprint_narrator import __version__
from sprint_narrator.config import display_config, load_config, save_config

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


@app.command()
def run(
    source: list[str] = typer.Option(
        ..., "--source", "-s", help="Data source: github, linear, jira."
    ),
    since: str | None = typer.Option(None, help="Start date (YYYY-MM-DD). Defaults to 7 days ago."),
    until: str | None = typer.Option(None, help="End date (YYYY-MM-DD). Defaults to today."),
    team: str | None = typer.Option(None, help="Team ID or name."),
    model: str = typer.Option("llama3.1:8b", help="Ollama model for narrative generation."),
    output: Path | None = typer.Option(None, "-o", help="Output file path."),
    format: str = typer.Option("md", help="Output format: md or html."),
) -> None:
    """Generate a sprint summary from configured sources."""
    start = since or (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    end = until or datetime.now().strftime("%Y-%m-%d")

    console.print(f"[bold]Generating sprint summary ({start} to {end})...[/bold]")
    console.print(f"Sources: {', '.join(source)}")

    # TODO: Fetch from sources → aggregate → narrate → render (Phase 3)
    raise NotImplementedError("run command not yet implemented")


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

    for s in summaries:
        console.print(f"[bold]{s['date_range']}[/bold] — {s['sources']}")


@app.command()
def configure(
    github_token: str | None = typer.Option(None, help="GitHub personal access token."),
    github_repo: list[str] | None = typer.Option(None, help="GitHub repos (owner/repo)."),
    linear_token: str | None = typer.Option(None, help="Linear API key."),
    linear_team_id: str | None = typer.Option(None, help="Linear team ID."),
    jira_url: str | None = typer.Option(None, help="Jira instance URL."),
    jira_email: str | None = typer.Option(None, help="Jira account email."),
    jira_token: str | None = typer.Option(None, help="Jira API token."),
    jira_project_key: str | None = typer.Option(None, help="Jira project key."),
    default_model: str | None = typer.Option(None, help="Default Ollama model."),
    show: bool = typer.Option(False, help="Show current config (tokens masked)."),
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
