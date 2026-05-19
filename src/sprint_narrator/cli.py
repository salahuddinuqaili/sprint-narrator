from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from sprint_narrator import __version__

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
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True,
    ),
) -> None:
    pass


@app.command()
def run(
    source: list[str] = typer.Option(..., "--source", "-s", help="Data source: github, linear, jira."),
    since: Optional[str] = typer.Option(None, help="Start date (YYYY-MM-DD). Defaults to 7 days ago."),
    until: Optional[str] = typer.Option(None, help="End date (YYYY-MM-DD). Defaults to today."),
    team: Optional[str] = typer.Option(None, help="Team ID or name."),
    model: str = typer.Option("llama3.1:8b", help="Ollama model for narrative generation."),
    output: Optional[Path] = typer.Option(None, "-o", help="Output file path."),
    format: str = typer.Option("md", help="Output format: md or html."),
) -> None:
    """Generate a sprint summary from configured sources."""
    start = since or (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    end = until or datetime.now().strftime("%Y-%m-%d")

    console.print(f"[bold]Generating sprint summary ({start} to {end})...[/bold]")
    console.print(f"Sources: {', '.join(source)}")

    # TODO: Fetch from sources → aggregate → narrate → render
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
    github_token: Optional[str] = typer.Option(None, help="GitHub personal access token."),
    linear_token: Optional[str] = typer.Option(None, help="Linear API key."),
    jira_url: Optional[str] = typer.Option(None, help="Jira instance URL."),
    jira_token: Optional[str] = typer.Option(None, help="Jira API token."),
    default_model: Optional[str] = typer.Option(None, help="Default Ollama model."),
) -> None:
    """Set API tokens and defaults."""
    # TODO: Read/write config from ~/.config/sprint-narrator/config.toml
    raise NotImplementedError("configure command not yet implemented")
