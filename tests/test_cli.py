from typer.testing import CliRunner

from sprint_narrator.cli import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "sprint-narrator v" in result.stdout


def test_run_requires_source() -> None:
    result = runner.invoke(app, ["run"])
    assert result.exit_code != 0
