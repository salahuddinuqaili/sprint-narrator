from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from sprint_narrator.aggregator import SprintData

TEMPLATE_DIR = Path(__file__).parent / "templates"

_TEMPLATE_MAP: dict[str, str] = {
    "md": "summary.md.j2",
    "html": "summary.html.j2",
}


def render_output(
    narrative: str,
    sprint_data: SprintData,
    fmt: str,
    since: str,
    until: str,
    sources: list[str],
) -> str:
    """Render narrative + sprint data using a Jinja2 template."""
    template_file = _TEMPLATE_MAP.get(fmt)
    if not template_file:
        raise ValueError(f"Unknown format '{fmt}'. Use: md, html")

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        keep_trailing_newline=True,
    )
    template = env.get_template(template_file)

    return template.render(
        narrative=narrative,
        since=since,
        until=until,
        sources=sources,
        features=sprint_data.features,
        bug_fixes=sprint_data.bug_fixes,
        in_progress=sprint_data.in_progress,
        blocked=sprint_data.blocked,
        stats=sprint_data.stats,
    )
