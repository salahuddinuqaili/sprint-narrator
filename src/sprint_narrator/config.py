from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import typer

CONFIG_DIR = Path.home() / ".config" / "sprint-narrator"
CONFIG_PATH = CONFIG_DIR / "config.toml"

# Env var prefix — e.g. SPRINT_NARRATOR_GITHUB_TOKEN
_ENV_PREFIX = "SPRINT_NARRATOR_"

_ENV_MAP: dict[str, str] = {
    "github_token": f"{_ENV_PREFIX}GITHUB_TOKEN",
    "linear_token": f"{_ENV_PREFIX}LINEAR_TOKEN",
    "linear_team_id": f"{_ENV_PREFIX}LINEAR_TEAM_ID",
    "jira_url": f"{_ENV_PREFIX}JIRA_URL",
    "jira_email": f"{_ENV_PREFIX}JIRA_EMAIL",
    "jira_token": f"{_ENV_PREFIX}JIRA_TOKEN",
    "jira_project_key": f"{_ENV_PREFIX}JIRA_PROJECT_KEY",
    "default_model": f"{_ENV_PREFIX}DEFAULT_MODEL",
}


@dataclass
class AppConfig:
    github_token: str | None = None
    github_repos: list[str] = field(default_factory=list)
    linear_token: str | None = None
    linear_team_id: str | None = None
    jira_url: str | None = None
    jira_email: str | None = None
    jira_token: str | None = None
    jira_project_key: str | None = None
    default_model: str = "llama3.1:8b"


def load_config() -> AppConfig:
    """Load config from TOML file with env var fallbacks.

    Priority: env vars > config file > defaults.
    """
    file_data: dict = {}
    if CONFIG_PATH.exists():
        file_data = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    config = AppConfig()

    # Apply file values first
    for fld in (
        "github_token",
        "linear_token",
        "linear_team_id",
        "jira_url",
        "jira_email",
        "jira_token",
        "jira_project_key",
        "default_model",
    ):
        if fld in file_data:
            setattr(config, fld, file_data[fld])

    if "github_repos" in file_data:
        repos = file_data["github_repos"]
        config.github_repos = repos if isinstance(repos, list) else [repos]

    # Env vars override file values
    for fld, env_key in _ENV_MAP.items():
        val = os.environ.get(env_key)
        if val:
            setattr(config, fld, val)

    # github_repos from env is comma-separated
    repos_env = os.environ.get(f"{_ENV_PREFIX}GITHUB_REPOS")
    if repos_env:
        config.github_repos = [r.strip() for r in repos_env.split(",") if r.strip()]

    return config


def save_config(config: AppConfig) -> None:
    """Write config to TOML file. Manual serialisation to avoid tomli-w dep."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for fld in (
        "github_token",
        "linear_token",
        "linear_team_id",
        "jira_url",
        "jira_email",
        "jira_token",
        "jira_project_key",
        "default_model",
    ):
        val = getattr(config, fld)
        if val is not None:
            lines.append(f'{fld} = "{val}"')

    if config.github_repos:
        items = ", ".join(f'"{r}"' for r in config.github_repos)
        lines.append(f"github_repos = [{items}]")

    CONFIG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _mask_token(token: str | None) -> str:
    """Show only last 4 chars of a token."""
    if not token:
        return "(not set)"
    if len(token) <= 4:
        return "****"
    return "****" + token[-4:]


def get_token_for_source(source: str, config: AppConfig) -> str:
    """Return the required token for a source, or raise with setup instructions."""
    token_fields: dict[str, tuple[str, str]] = {
        "github": (
            "github_token",
            "sprint-narrator configure --github-token <token>\n"
            f"  or: set {_ENV_MAP['github_token']}=<token>",
        ),
        "linear": (
            "linear_token",
            "sprint-narrator configure --linear-token <token>\n"
            f"  or: set {_ENV_MAP['linear_token']}=<token>",
        ),
        "jira": (
            "jira_token",
            "sprint-narrator configure --jira-token <token>\n"
            f"  or: set {_ENV_MAP['jira_token']}=<token>",
        ),
    }

    if source not in token_fields:
        raise typer.BadParameter(f"Unknown source: {source}. Use: github, linear, jira.")

    field_name, hint = token_fields[source]
    token = getattr(config, field_name)
    if not token:
        raise typer.BadParameter(f"{source.title()} token not configured.\n  Set via: {hint}")
    return token


def display_config(config: AppConfig) -> dict[str, str]:
    """Return config as a dict with masked tokens for display."""
    return {
        "github_token": _mask_token(config.github_token),
        "github_repos": ", ".join(config.github_repos) if config.github_repos else "(not set)",
        "linear_token": _mask_token(config.linear_token),
        "linear_team_id": config.linear_team_id or "(not set)",
        "jira_url": config.jira_url or "(not set)",
        "jira_email": config.jira_email or "(not set)",
        "jira_token": _mask_token(config.jira_token),
        "jira_project_key": config.jira_project_key or "(not set)",
        "default_model": config.default_model,
    }
