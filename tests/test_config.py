from pathlib import Path

import pytest
import typer

from sprint_narrator.config import (
    AppConfig,
    display_config,
    get_token_for_source,
    load_config,
    save_config,
)


@pytest.fixture()
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect config to a temp directory."""
    config_path = tmp_path / "config.toml"
    monkeypatch.setattr("sprint_narrator.config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr("sprint_narrator.config.CONFIG_PATH", config_path)
    return tmp_path


def test_load_config_defaults(config_dir: Path) -> None:
    config = load_config()
    assert config.github_token is None
    assert config.github_repos == []
    assert config.default_model == "llama3.1:8b"


def test_load_config_from_file(config_dir: Path) -> None:
    toml = (
        'github_token = "ghp_abc123"\n'
        'github_repos = ["owner/repo1", "owner/repo2"]\n'
        'default_model = "mistral"\n'
    )
    (config_dir / "config.toml").write_text(toml, encoding="utf-8")

    config = load_config()
    assert config.github_token == "ghp_abc123"
    assert config.github_repos == ["owner/repo1", "owner/repo2"]
    assert config.default_model == "mistral"


def test_env_var_overrides_file(config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    toml = 'github_token = "from_file"\n'
    (config_dir / "config.toml").write_text(toml, encoding="utf-8")
    monkeypatch.setenv("SPRINT_NARRATOR_GITHUB_TOKEN", "from_env")

    config = load_config()
    assert config.github_token == "from_env"


def test_env_var_github_repos(config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPRINT_NARRATOR_GITHUB_REPOS", "a/b, c/d")
    config = load_config()
    assert config.github_repos == ["a/b", "c/d"]


def test_save_config_creates_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    nested = tmp_path / "sub" / "dir"
    monkeypatch.setattr("sprint_narrator.config.CONFIG_DIR", nested)
    monkeypatch.setattr("sprint_narrator.config.CONFIG_PATH", nested / "config.toml")

    config = AppConfig(github_token="ghp_test", github_repos=["o/r"])
    save_config(config)

    assert (nested / "config.toml").exists()
    content = (nested / "config.toml").read_text(encoding="utf-8")
    assert 'github_token = "ghp_test"' in content
    assert 'github_repos = ["o/r"]' in content


def test_save_and_reload_roundtrip(config_dir: Path) -> None:
    original = AppConfig(
        github_token="ghp_xyz",
        github_repos=["a/b", "c/d"],
        linear_token="lin_123",
        default_model="phi3",
    )
    save_config(original)
    loaded = load_config()

    assert loaded.github_token == original.github_token
    assert loaded.github_repos == original.github_repos
    assert loaded.linear_token == original.linear_token
    assert loaded.default_model == original.default_model


def test_get_token_for_source_missing() -> None:
    config = AppConfig()
    with pytest.raises(typer.BadParameter, match="(?i)github token not configured"):
        get_token_for_source("github", config)


def test_get_token_for_source_present() -> None:
    config = AppConfig(github_token="ghp_abc")
    assert get_token_for_source("github", config) == "ghp_abc"


def test_get_token_for_source_unknown() -> None:
    config = AppConfig()
    with pytest.raises(typer.BadParameter, match="Unknown source"):
        get_token_for_source("notion", config)


def test_display_config_masks_tokens() -> None:
    config = AppConfig(github_token="ghp_abcdefgh1234")
    masked = display_config(config)
    assert masked["github_token"] == "****1234"
    assert masked["linear_token"] == "(not set)"
