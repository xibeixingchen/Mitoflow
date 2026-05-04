"""Tests for MitoFlow AI CLI entry point."""

from typer.testing import CliRunner

from mitoflow.cli import app


def test_ai_chat_one_shot_fake_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("MITOFLOW_AI_PROVIDER", "fake")
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "ai-chat",
            "--prompt",
            "hello",
            "--sessions-dir",
            str(tmp_path / "sessions"),
            "--workspace",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "MitoFlow AI is configured with the fake provider" in result.output


def test_ai_chat_lists_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("MITOFLOW_AI_PROVIDER", "fake")
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "ai-chat",
            "--prompt",
            "list tools",
            "--sessions-dir",
            str(tmp_path / "sessions"),
            "--workspace",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
